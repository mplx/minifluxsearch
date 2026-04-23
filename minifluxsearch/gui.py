# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

import locale
import os
import unicodedata
from pathlib import Path
import threading
import tkinter.font as tkfont
import webbrowser
from datetime import datetime, timezone
from typing import Optional
import tkinter as tk
from tkinter import messagebox, ttk

_THEMES_DIR = Path(__file__).parent / "themes"
_ICON_PATH = Path(__file__).parent / "icon.png"
_THEME_LABELS = {
    "forest-light": "Forest Light",
    "forest-dark":  "Forest Dark",
    "default":      "System",
}
_THEME_KEYS = {v: k for k, v in _THEME_LABELS.items()}
_sourced_themes: set[str] = set()

from tkcalendar import DateEntry

from . import __version__
from .api import MinifluxAPIError, MinifluxClient
from .config import (CONFIG_PATH, Config, GuiSettings, load_config,
                     load_gui_settings, save_config, save_gui_settings)
from .models import Category, Entry, Feed
from .search import filter_by_keywords


class App:
    def __init__(self, root: tk.Tk, client: MinifluxClient) -> None:
        self._client = client
        self._root = root
        self._feeds: list[Feed] = []
        self._categories: list[Category] = []
        self._entries: list[Entry] = []
        self._item_entries: dict[str, Entry] = {}
        self._sort_col = "date"
        self._sort_rev = False
        self._keyword_history: list[str] = []
        self._current_theme: str = "forest-light"

        root.title("minifluxsearch")
        root.minsize(920, 560)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._apply_gui_settings(load_gui_settings())
        self._load_scope()

    # -- UI construction -------------------------------------------------------

    def _build(self) -> None:
        self._build_topbar()
        self._build_statusbar()

        pane = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        left = ttk.Frame(pane, width=250)
        left.pack_propagate(False)
        pane.add(left, weight=0)

        right = ttk.Frame(pane)
        pane.add(right, weight=1)

        self._build_left(left)
        self._build_results(right)

    def _build_topbar(self) -> None:
        bar = ttk.Frame(self._root, padding=(6, 6, 6, 4))
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="Keywords:").pack(side=tk.LEFT)
        self._kw_var = tk.StringVar()
        self._kw_combo = ttk.Combobox(bar, textvariable=self._kw_var, width=40)
        self._kw_combo.pack(side=tk.LEFT, padx=(4, 8))
        self._kw_combo.bind("<Return>", lambda _: self._search())
        self._kw_combo.focus()

        ttk.Button(bar, text="Search", command=self._search).pack(side=tk.LEFT)

        self._any_kw_var = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Any keyword",
                        variable=self._any_kw_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(bar, text="Mark as read",
                   command=self._mark_selected_read).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(bar, text="Mark as unread",
                   command=self._mark_selected_unread).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(bar, text="Config",
                   command=self._open_settings).pack(side=tk.LEFT, padx=(4, 0))

    def _build_statusbar(self) -> None:
        self._status_var = tk.StringVar(value="Loading…")
        ttk.Label(self._root, textvariable=self._status_var, anchor=tk.W,
                  relief=tk.SUNKEN, padding=(4, 2)).pack(fill=tk.X, side=tk.BOTTOM)

    def _build_left(self, parent: ttk.Frame) -> None:
        # -- scope -------------------------------------------------------------
        scope = ttk.LabelFrame(parent, text="Scope", padding=4)
        scope.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        nb = ttk.Notebook(scope)
        nb.pack(fill=tk.BOTH, expand=True)

        feeds_tab = ttk.Frame(nb)
        nb.add(feeds_tab, text="Feeds")
        self._feeds_lb = self._make_listbox(feeds_tab)
        self._feeds_lb.bind("<Double-Button-1>", lambda _: (
            self._cats_lb.selection_clear(0, tk.END), self._search()))

        cats_tab = ttk.Frame(nb)
        nb.add(cats_tab, text="Categories")
        self._cats_lb = self._make_listbox(cats_tab)
        self._cats_lb.bind("<Double-Button-1>", lambda _: (
            self._feeds_lb.selection_clear(0, tk.END), self._search()))

        ttk.Button(scope, text="Clear selection",
                   command=self._clear_scope).pack(fill=tk.X, pady=(4, 0))

        # -- filters -----------------------------------------------------------
        flt = ttk.LabelFrame(parent, text="Filters", padding=4)
        flt.pack(fill=tk.X, padx=4, pady=(0, 4))
        flt.columnconfigure(1, weight=1)

        ttk.Label(flt, text="Status:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self._filter_status_var = tk.StringVar(value="all")
        ttk.Combobox(flt, textvariable=self._filter_status_var,
                     values=["all", "unread", "read"],
                     state="readonly", width=9).grid(
            row=0, column=1, sticky=tk.EW, padx=(4, 0))

        self._starred_var = tk.BooleanVar()
        ttk.Checkbutton(flt, text="Starred only",
                        variable=self._starred_var).grid(
            row=1, column=0, columnspan=2, sticky=tk.W)

        # date pickers with enable checkbox
        self._after_enabled = tk.BooleanVar()
        self._before_enabled = tk.BooleanVar()

        after_frame = ttk.Frame(flt)
        after_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=2)
        ttk.Checkbutton(after_frame, variable=self._after_enabled).pack(side=tk.LEFT)
        ttk.Label(after_frame, text="After:", width=6).pack(side=tk.LEFT)
        self._after_picker = DateEntry(after_frame, width=10, date_pattern="yyyy-mm-dd",
                                       firstweekday="monday")
        self._after_picker.pack(side=tk.LEFT, padx=(2, 0))

        before_frame = ttk.Frame(flt)
        before_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=2)
        ttk.Checkbutton(before_frame, variable=self._before_enabled).pack(side=tk.LEFT)
        ttk.Label(before_frame, text="Before:", width=6).pack(side=tk.LEFT)
        self._before_picker = DateEntry(before_frame, width=10, date_pattern="yyyy-mm-dd",
                                        firstweekday="monday")
        self._before_picker.pack(side=tk.LEFT, padx=(2, 0))

        # -- options -----------------------------------------------------------
        opt = ttk.LabelFrame(parent, text="Options", padding=4)
        opt.pack(fill=tk.X, padx=4, pady=(0, 4))
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Fetch limit:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self._fetch_limit_var = tk.IntVar(value=1000)
        ttk.Spinbox(opt, from_=10, to=10000, increment=100,
                    textvariable=self._fetch_limit_var, width=7).grid(
            row=0, column=1, sticky=tk.EW, padx=(4, 0))

        ttk.Label(opt, text="Max results:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self._max_results_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self._max_results_var, width=7).grid(
            row=1, column=1, sticky=tk.EW, padx=(4, 0))

    def _build_results(self, parent: ttk.Frame) -> None:
        cols = ("date", "starred", "title", "url")
        self._tree = ttk.Treeview(parent, columns=cols, show="headings",
                                   selectmode="extended")

        for col, label, width, stretch in (
            ("date",    "Date",  90, False),
            ("starred", "",      24, False),
            ("title",   "Title", 356, True),
            ("url",     "URL",   260, True),
        ):
            self._tree.heading(col, text=label,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, stretch=stretch)

        # bold tag for unread entries
        bold_font = tkfont.nametofont("TkDefaultFont").copy()
        bold_font.configure(weight="bold")
        self._tree.tag_configure("unread", font=bold_font)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-1>", self._open_url)
        self._tree.bind("<Return>", self._open_url)
        self._tree.bind("<Button-3>", self._show_context_menu)
        self._tree.bind("<Control-a>", lambda _: self._tree.selection_set(
            self._tree.get_children()))
        self._tree.bind("<Shift-Up>",   lambda _: self._extend_selection(-1))
        self._tree.bind("<Shift-Down>", lambda _: self._extend_selection(1))
        self._tree.bind("r", lambda _: self._toggle_status(self._selected_entries()))
        self._tree.bind("s", lambda _: self._toggle_starred(self._selected_entries()))
        self._tree.bind("k", lambda _: self._kw_combo.focus_set())

    def _make_listbox(self, parent: ttk.Frame) -> tk.Listbox:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        lb = tk.Listbox(frame, selectmode=tk.EXTENDED, exportselection=False,
                        yscrollcommand=sb.set, height=8, activestyle="dotbox")
        lb.bind("<Control-a>", lambda _: lb.selection_set(0, tk.END))
        sb.config(command=lb.yview)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return lb

    # -- data loading ----------------------------------------------------------

    def _load_scope(self) -> None:
        def task() -> None:
            try:
                feeds = self._client.get_feeds()
                cats = self._client.get_categories()
                self._root.after(0, lambda: self._populate_scope(feeds, cats))
            except MinifluxAPIError as e:
                self._root.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def _populate_scope(self, feeds: list[Feed], cats: list[Category]) -> None:
        self._feeds = sorted(
            (f for f in feeds if not f.disabled),
            key=lambda f: locale.strxfrm(unicodedata.normalize("NFKD", f.title.casefold())),
        )
        self._categories = sorted(cats, key=lambda c: locale.strxfrm(unicodedata.normalize("NFKD", c.title.casefold())))

        for feed in self._feeds:
            label = feed.title
            if feed.category:
                label += f"  [{feed.category.title}]"
            self._feeds_lb.insert(tk.END, label)

        for cat in self._categories:
            self._cats_lb.insert(tk.END, cat.title)

        self._set_status(
            f"minifluxsearch {__version__} by mplx | © 2026 | GNU LGPLv3"
        )

    # -- search ----------------------------------------------------------------

    def _search(self) -> None:
        keywords = self._kw_var.get().split()

        # Update keyword history only when a keyword was entered
        search_str = self._kw_var.get().strip()
        if search_str:
            if search_str in self._keyword_history:
                self._keyword_history.remove(search_str)
            self._keyword_history.insert(0, search_str)
            self._keyword_history = self._keyword_history[:10]
            self._kw_combo["values"] = self._keyword_history
            self._persist_gui_settings()

        feed_ids = [self._feeds[i].id for i in self._feeds_lb.curselection()]
        cat_ids = [self._categories[i].id for i in self._cats_lb.curselection()]

        status = self._filter_status_var.get()
        api_status = None if status == "all" else status
        starred = True if self._starred_var.get() else None

        after: Optional[datetime] = None
        if self._after_enabled.get():
            d = self._after_picker.get_date()
            after = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)

        before: Optional[datetime] = None
        if self._before_enabled.get():
            d = self._before_picker.get_date()
            before = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)

        try:
            fetch_limit = max(1, int(self._fetch_limit_var.get()))
        except (ValueError, tk.TclError):
            fetch_limit = 1000

        max_str = self._max_results_var.get().strip()
        max_results: Optional[int] = int(max_str) if max_str.isdigit() else None

        match_any = self._any_kw_var.get()

        self._set_status("Searching…")
        self._clear_tree()

        def task() -> None:
            try:
                entries = self._client.get_entries(
                    feed_ids=feed_ids or None,
                    category_ids=cat_ids or None,
                    status=api_status,
                    starred=starred,
                    after=after,
                    before=before,
                    limit=fetch_limit,
                )
                results = filter_by_keywords(entries, keywords, match_any=match_any)
                results.sort(key=lambda e: (e.published_at, e.title.lower()))
                if max_results is not None:
                    results = results[:max_results]
                self._root.after(0, lambda: self._show_results(results))
            except MinifluxAPIError as e:
                self._root.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def _show_results(self, entries: list[Entry]) -> None:
        self._entries = entries
        self._sort_col = "date"
        self._sort_rev = False
        self._populate_tree(entries)
        n = len(entries)
        self._set_status(f"{n} result{'s' if n != 1 else ''} found")

    # -- treeview --------------------------------------------------------------

    def _populate_tree(self, entries: list[Entry]) -> None:
        self._clear_tree()
        for entry in entries:
            date_str = (entry.published_at.strftime("%Y-%m-%d")
                        if entry.published_at.year > 1 else "")
            star_str = "★" if entry.starred else ""
            tags = ("unread",) if entry.status == "unread" else ()
            iid = self._tree.insert("", tk.END,
                                    values=(date_str, star_str, entry.title, entry.url),
                                    tags=tags)
            self._item_entries[iid] = entry

    def _clear_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._item_entries.clear()

    def _sort_by(self, col: str) -> None:
        self._sort_rev = (col == self._sort_col) and not self._sort_rev
        self._sort_col = col
        key = {"date": lambda e: e.published_at,
               "title": lambda e: e.title.lower(),
               "url": lambda e: e.url.lower()}[col]
        self._entries.sort(key=key, reverse=self._sort_rev)
        self._populate_tree(self._entries)

    def _open_url(self, _event: Optional[tk.Event]) -> None:
        selected = self._selected_entries()
        if not selected:
            return
        for _, entry in selected:
            webbrowser.open(entry.url)
        unread = [(iid, e) for iid, e in selected if e.status == "unread"]
        if unread:
            self._set_entries_status(unread, "read")

    # -- context menu ----------------------------------------------------------

    def _show_context_menu(self, event: tk.Event) -> None:
        clicked = self._tree.identify_row(event.y)
        if not clicked:
            return
        if clicked not in self._tree.selection():
            self._tree.selection_set(clicked)
        selected = self._selected_entries()
        if not selected:
            return

        n = len(selected)
        suffix = f" ({n})" if n > 1 else ""
        menu = tk.Menu(self._root, tearoff=0)
        menu.add_command(label=f"Open in browser{suffix}",
                         command=lambda: self._open_url(None))
        menu.add_separator()
        menu.add_command(label=f"Mark as read{suffix}",
                         command=lambda: self._set_entries_status(selected, "read"))
        menu.add_command(label=f"Mark as unread{suffix}",
                         command=lambda: self._set_entries_status(selected, "unread"))
        menu.add_separator()
        menu.add_command(label=f"Star{suffix}",
                         command=lambda: self._star_entries(selected, starred=True))
        menu.add_command(label=f"Unstar{suffix}",
                         command=lambda: self._star_entries(selected, starred=False))
        menu.tk_popup(event.x_root, event.y_root)

    def _toggle_status(self, entries: list[tuple[str, Entry]]) -> None:
        if not entries:
            return
        all_read = all(e.status == "read" for _, e in entries)
        self._set_entries_status(entries, "unread" if all_read else "read")

    def _toggle_starred(self, entries: list[tuple[str, Entry]]) -> None:
        if not entries:
            return
        all_starred = all(e.starred for _, e in entries)
        self._star_entries(entries, starred=not all_starred)

    def _set_entries_status(self, entries: list[tuple[str, Entry]], status: str) -> None:
        to_update = [(iid, e) for iid, e in entries if e.status != status]
        if not to_update:
            return

        def task() -> None:
            try:
                self._client.update_entry_status([e.id for _, e in to_update], status)
                for iid, entry in to_update:
                    entry.status = status
                    self._root.after(0, lambda i=iid, e=entry: self._refresh_row(i, e))
                n = len(to_update)
                self._root.after(0, lambda: self._set_status(
                    f"Marked {n} entr{'ies' if n != 1 else 'y'} as {status}"))
            except MinifluxAPIError as e:
                self._root.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def _star_entries(self, entries: list[tuple[str, Entry]], starred: bool) -> None:
        to_toggle = [(iid, e) for iid, e in entries if e.starred != starred]
        if not to_toggle:
            return

        def task() -> None:
            errors: list[str] = []
            for iid, entry in to_toggle:
                try:
                    self._client.toggle_entry_starred(entry.id)
                    entry.starred = starred
                    self._root.after(0, lambda i=iid, e=entry: self._refresh_row(i, e))
                except MinifluxAPIError as exc:
                    errors.append(str(exc))
            n = len(to_toggle)
            verb = "Starred" if starred else "Unstarred"
            msg = errors[0] if errors else f"{verb} {n} entr{'ies' if n != 1 else 'y'}"
            self._root.after(0, lambda: self._set_status(msg))

        threading.Thread(target=task, daemon=True).start()

    def _refresh_row(self, iid: str, entry: Entry) -> None:
        tags = ("unread",) if entry.status == "unread" else ()
        star_str = "★" if entry.starred else ""
        self._tree.item(iid, tags=tags,
                        values=(*self._tree.item(iid, "values")[:1], star_str,
                                *self._tree.item(iid, "values")[2:]))

    # -- gui settings persistence ----------------------------------------------

    def _apply_gui_settings(self, s: GuiSettings) -> None:
        self._keyword_history = list(s.keyword_history)
        self._kw_combo["values"] = self._keyword_history

        self._filter_status_var.set(s.status)
        self._starred_var.set(s.starred)
        self._any_kw_var.set(s.any_keyword)

        self._fetch_limit_var.set(s.fetch_limit)
        self._max_results_var.set(s.max_results)

        self._after_enabled.set(s.after_enabled)
        if s.after_date:
            try:
                from datetime import date as _date
                self._after_picker.set_date(_date.fromisoformat(s.after_date))
            except ValueError:
                pass

        self._current_theme = s.theme

        if s.window_geometry:
            self._root.geometry(s.window_geometry)

        self._before_enabled.set(s.before_enabled)
        if s.before_date:
            try:
                from datetime import date as _date
                self._before_picker.set_date(_date.fromisoformat(s.before_date))
            except ValueError:
                pass

    def _collect_gui_settings(self) -> GuiSettings:
        after_date = ""
        if self._after_enabled.get():
            try:
                after_date = self._after_picker.get_date().isoformat()
            except Exception:
                pass
        before_date = ""
        if self._before_enabled.get():
            try:
                before_date = self._before_picker.get_date().isoformat()
            except Exception:
                pass
        return GuiSettings(
            status=self._filter_status_var.get(),
            starred=self._starred_var.get(),
            fetch_limit=self._fetch_limit_var.get(),
            max_results=self._max_results_var.get().strip(),
            any_keyword=self._any_kw_var.get(),
            after_enabled=self._after_enabled.get(),
            after_date=after_date,
            before_enabled=self._before_enabled.get(),
            before_date=before_date,
            keyword_history=self._keyword_history,
            window_geometry=self._root.geometry(),
            theme=self._current_theme,
        )

    def _persist_gui_settings(self) -> None:
        try:
            save_gui_settings(self._collect_gui_settings())
        except Exception:
            pass

    def _on_close(self) -> None:
        self._persist_gui_settings()
        self._root.destroy()

    # -- settings dialog -------------------------------------------------------

    def _open_settings(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("Settings")
        win.resizable(False, False)
        win.grab_set()

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        # Read current file values (bypass env vars so user sees what's on disk)
        file_url, file_key = "", ""
        if CONFIG_PATH.exists():
            try:
                cfg = load_config(CONFIG_PATH)
                file_url, file_key = cfg.base_url, cfg.api_key
            except RuntimeError:
                pass

        ttk.Label(frame, text="Miniflux URL:").grid(
            row=0, column=0, sticky=tk.W, padx=8, pady=4)
        url_var = tk.StringVar(value=file_url)
        ttk.Entry(frame, textvariable=url_var, width=42).grid(
            row=0, column=1, sticky=tk.EW, padx=8, pady=4)

        ttk.Label(frame, text="API Key:").grid(
            row=1, column=0, sticky=tk.W, padx=8, pady=4)
        key_var = tk.StringVar(value=file_key)
        key_entry = ttk.Entry(frame, textvariable=key_var, width=42, show="•")
        key_entry.grid(row=1, column=1, sticky=tk.EW, padx=8, pady=4)

        show_var = tk.BooleanVar()
        ttk.Checkbutton(
            frame, text="Show API key", variable=show_var,
            command=lambda: key_entry.config(show="" if show_var.get() else "•"),
        ).grid(row=2, column=1, sticky=tk.W, padx=8)

        # Warn when env vars are active (file changes won't take effect until cleared)
        env_warns = [v for v in ("MINIFLUX_URL", "MINIFLUX_API_KEY") if os.environ.get(v)]
        if env_warns:
            msg = "Environment variable(s) " + ", ".join(env_warns) + \
                  " are set and override the config file."
            ttk.Label(frame, text=msg, foreground="orange",
                      wraplength=360).grid(row=3, column=0, columnspan=2,
                                           sticky=tk.W, padx=8, pady=(4, 0))

        ttk.Separator(frame).grid(row=4, column=0, columnspan=2,
                                  sticky=tk.EW, pady=(12, 4))

        # theme selector
        ttk.Label(frame, text="Theme:").grid(
            row=5, column=0, sticky=tk.W, padx=8, pady=4)
        theme_frame = ttk.Frame(frame)
        theme_frame.grid(row=5, column=1, sticky=tk.EW, padx=8, pady=4)
        theme_var = tk.StringVar(value=_THEME_LABELS.get(self._current_theme, "Forest Light"))
        ttk.Combobox(theme_frame, textvariable=theme_var,
                     values=list(_THEME_LABELS.values()),
                     state="readonly", width=16).pack(side=tk.LEFT)
        ttk.Label(theme_frame,
                  text="  Forest Theme © 2021 rdbende <rdbende@gmail.com>",
                  foreground="gray").pack(side=tk.LEFT)

        ttk.Separator(frame).grid(row=6, column=0, columnspan=2,
                                  sticky=tk.EW, pady=(12, 4))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky=tk.E)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="Save", command=lambda: self._save_settings(
            win, url_var.get().strip(), key_var.get().strip(),
            _THEME_KEYS.get(theme_var.get(), "forest-light"),
        )).pack(side=tk.LEFT)

        win.bind("<Return>", lambda _: self._save_settings(
            win, url_var.get().strip(), key_var.get().strip(),
            _THEME_KEYS.get(theme_var.get(), "forest-light"),
        ))
        win.bind("<Escape>", lambda _: win.destroy())

    def _save_settings(self, win: tk.Toplevel, url: str, api_key: str, theme: str) -> None:
        if not url or not api_key:
            messagebox.showerror("Error", "URL and API key are required.", parent=win)
            return
        try:
            save_config(url, api_key)
        except OSError as e:
            messagebox.showerror("Error", f"Could not write config file:\n{e}", parent=win)
            return

        if theme != self._current_theme:
            self._current_theme = theme
            _apply_theme(self._root, theme)
            self._persist_gui_settings()

        # Reconnect with new credentials (env vars take priority at runtime,
        # so build Config directly from the form values)
        self._client = MinifluxClient(Config(base_url=url.rstrip("/"), api_key=api_key))
        win.destroy()
        self._set_status("Settings saved - reloading…")
        self._feeds_lb.delete(0, tk.END)
        self._cats_lb.delete(0, tk.END)
        self._load_scope()

    # -- helpers ---------------------------------------------------------------

    def _mark_selected_read(self) -> None:
        entries = self._selected_entries() or list(self._item_entries.items())
        self._set_entries_status(entries, "read")

    def _mark_selected_unread(self) -> None:
        entries = self._selected_entries() or list(self._item_entries.items())
        self._set_entries_status(entries, "unread")

    def _extend_selection(self, direction: int) -> str:
        items = self._tree.get_children()
        if not items:
            return "break"
        focused = self._tree.focus()
        if focused not in items:
            focused = items[0]
        idx = items.index(focused)
        new_idx = max(0, min(len(items) - 1, idx + direction))
        new_item = items[new_idx]
        self._tree.focus(new_item)
        self._tree.selection_add(new_item)
        self._tree.see(new_item)
        return "break"

    def _selected_entries(self) -> list[tuple[str, Entry]]:
        return [(iid, self._item_entries[iid])
                for iid in self._tree.selection()
                if iid in self._item_entries]

    def _clear_scope(self) -> None:
        self._feeds_lb.selection_clear(0, tk.END)
        self._cats_lb.selection_clear(0, tk.END)

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")
    try:
        config = load_config()
        client = MinifluxClient(config)
    except RuntimeError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Configuration Error", str(e))
        root.destroy()
        return

    root = tk.Tk()
    root.withdraw()
    _apply_theme(root, load_gui_settings().theme)
    if _ICON_PATH.exists():
        icon = tk.PhotoImage(file=str(_ICON_PATH))
        root.iconphoto(True, icon)
    App(root, client)
    root.deiconify()
    root.mainloop()


def _apply_theme(root: tk.Tk, theme: str = "forest-light") -> None:
    if theme in ("forest-light", "forest-dark"):
        if theme not in _sourced_themes:
            tcl = _THEMES_DIR / f"{theme}.tcl"
            if tcl.exists():
                root.tk.call("source", str(tcl))
                _sourced_themes.add(theme)
        if theme in _sourced_themes:
            ttk.Style(root).theme_use(theme)
    else:
        ttk.Style(root).theme_use("default")

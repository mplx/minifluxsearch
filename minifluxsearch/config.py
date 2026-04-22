# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    _config_base = Path(os.environ.get("APPDATA") or Path.home())
else:
    _config_base = Path.home() / ".config"

CONFIG_PATH = _config_base / "minifluxsearch" / "config.toml"


@dataclass
class Config:
    base_url: str
    api_key: str


@dataclass
class GuiSettings:
    status: str = "all"
    starred: bool = False
    fetch_limit: int = 1000
    max_results: str = ""
    any_keyword: bool = False
    after_enabled: bool = False
    after_date: str = ""
    before_enabled: bool = False
    before_date: str = ""
    keyword_history: list[str] = field(default_factory=list)
    window_geometry: str = ""
    theme: str = "forest-light"


# -- TOML helpers --------------------------------------------------------------

def _toml_value(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(i) for i in v) + "]"
    return f'"{v}"'


def _read_raw(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _write_toml(sections: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section, kvs in sections.items():
        lines.append(f"[{section}]")
        for k, v in kvs.items():
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# -- Public API ----------------------------------------------------------------

def save_config(url: str, api_key: str, path: Path = CONFIG_PATH) -> None:
    data = _read_raw(path)
    data["miniflux"] = {"url": url, "api_key": api_key}
    _write_toml(data, path)


def load_gui_settings(path: Path = CONFIG_PATH) -> GuiSettings:
    gui = _read_raw(path).get("gui", {})
    return GuiSettings(
        status=str(gui.get("status", "all")),
        starred=bool(gui.get("starred", False)),
        fetch_limit=int(gui.get("fetch_limit", 1000)),
        max_results=str(gui.get("max_results", "")),
        any_keyword=bool(gui.get("any_keyword", False)),
        after_enabled=bool(gui.get("after_enabled", False)),
        after_date=str(gui.get("after_date", "")),
        before_enabled=bool(gui.get("before_enabled", False)),
        before_date=str(gui.get("before_date", "")),
        keyword_history=list(gui.get("keyword_history", []))[:10],
        window_geometry=str(gui.get("window_geometry", "")),
        theme=str(gui.get("theme", "forest-light")),
    )


def save_gui_settings(settings: GuiSettings, path: Path = CONFIG_PATH) -> None:
    data = _read_raw(path)
    data["gui"] = {
        "status": settings.status,
        "starred": settings.starred,
        "fetch_limit": settings.fetch_limit,
        "max_results": settings.max_results,
        "any_keyword": settings.any_keyword,
        "after_enabled": settings.after_enabled,
        "after_date": settings.after_date,
        "before_enabled": settings.before_enabled,
        "before_date": settings.before_date,
        "keyword_history": settings.keyword_history[:10],
        "window_geometry": settings.window_geometry,
        "theme": settings.theme,
    }
    _write_toml(data, path)


def load_config(config_path: Optional[Path] = None) -> Config:
    url = os.environ.get("MINIFLUX_URL")
    key = os.environ.get("MINIFLUX_API_KEY")

    if url and key:
        return Config(base_url=url.rstrip("/"), api_key=key)

    path = config_path or CONFIG_PATH
    if not path.exists():
        raise RuntimeError(
            "Miniflux credentials not found.\n"
            "Set MINIFLUX_URL and MINIFLUX_API_KEY environment variables, or create:\n"
            f"  {path}\n"
            "with:\n"
            "  [miniflux]\n"
            '  url = "https://your-miniflux-instance"\n'
            '  api_key = "your-api-key"'
        )

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise RuntimeError(f"Failed to parse config file {path}: {e}")

    try:
        section = data["miniflux"]
        return Config(
            base_url=section["url"].rstrip("/"),
            api_key=section["api_key"],
        )
    except KeyError as e:
        raise RuntimeError(f"Missing key {e} in config file {path}")
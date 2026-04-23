# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

import csv
import io
import locale
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import Optional

import click

from .api import MinifluxAPIError, MinifluxClient
from .config import load_config
from .models import Entry
from .search import filter_by_keywords


def _parse_date(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    try:
        d = date.fromisoformat(value)
        if end_of_day:
            return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    except ValueError:
        raise click.BadParameter(f"Cannot parse date {value!r}. Use YYYY-MM-DD.")


def _make_client() -> MinifluxClient:
    try:
        return MinifluxClient(load_config())
    except RuntimeError as e:
        raise click.ClickException(str(e))


def _entry_date(entry: Entry) -> str:
    return entry.published_at.strftime("%Y-%m-%d") if entry.published_at.year > 1 else ""


def _print_results(results: list[Entry], fmt: str) -> None:
    if fmt == "text":
        for entry in results:
            d = _entry_date(entry)
            prefix = f"[{d}] " if d else ""
            click.echo(f"{prefix}{entry.title}")
            click.echo(f"  {entry.url}")
            click.echo()

    elif fmt == "markdown":
        rows = [(_entry_date(e), e.title, e.url) for e in results]
        headers = ("Date", "Title", "URL")
        widths = [
            max(len(h), max(len(r[i]) for r in rows))
            for i, h in enumerate(headers)
        ]
        def md_row(cells: tuple[str, ...]) -> str:
            return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"
        click.echo(md_row(headers))
        click.echo("|-" + "-|-".join("-" * w for w in widths) + "-|")
        for row in rows:
            click.echo(md_row(row))

    elif fmt in ("csv", "tsv"):
        delimiter = "," if fmt == "csv" else "\t"
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=delimiter)
        writer.writerow(["date", "title", "url"])
        for entry in results:
            writer.writerow([_entry_date(entry), entry.title, entry.url])
        click.echo(buf.getvalue(), nl=False)

    elif fmt == "xml":
        root = ET.Element("entries")
        for entry in results:
            el = ET.SubElement(root, "entry")
            ET.SubElement(el, "date").text = _entry_date(entry)
            ET.SubElement(el, "title").text = entry.title
            ET.SubElement(el, "url").text = entry.url
        ET.indent(root)
        click.echo(ET.tostring(root, encoding="unicode", xml_declaration=False))


@click.group()
def main() -> None:
    """Search Miniflux v2 RSS entries by keyword."""
    locale.setlocale(locale.LC_ALL, "")


@main.command("categories")
def cmd_categories() -> None:
    """List all categories with their IDs."""
    client = _make_client()
    try:
        categories = client.get_categories()
    except MinifluxAPIError as e:
        raise click.ClickException(str(e))

    if not categories:
        click.echo("No categories found.", err=True)
        return

    for cat in sorted(categories, key=lambda c: locale.strxfrm(c.title)):
        click.echo(f"{cat.id:>6}  {cat.title}")


@main.command("feeds")
def cmd_feeds() -> None:
    """List all feeds with their IDs."""
    client = _make_client()
    try:
        feeds = client.get_feeds()
    except MinifluxAPIError as e:
        raise click.ClickException(str(e))

    if not feeds:
        click.echo("No feeds found.", err=True)
        return

    for feed in sorted((f for f in feeds if not f.disabled), key=lambda f: locale.strxfrm(f.title)):
        cat = f" [{feed.category.title}]" if feed.category else ""
        click.echo(f"{feed.id:>6}  {feed.title}{cat}")


@main.command("search")
@click.argument("keywords", nargs=-1, required=True)
@click.option("--feed-id", "feed_ids", type=int, multiple=True,
              help="Limit to this feed ID (repeatable).")
@click.option("--category-id", "category_ids", type=int, multiple=True,
              help="Limit to this category ID (repeatable). Ignored if --feed-id is set.")
@click.option("--status", type=click.Choice(["read", "unread", "all"]),
              default="all", show_default=True, help="Filter by read status.")
@click.option("--starred", is_flag=True, default=False,
              help="Only starred entries.")
@click.option("--after", "after_date", type=str, default=None, metavar="DATE",
              help="Only entries published after this date (YYYY-MM-DD, UTC).")
@click.option("--before", "before_date", type=str, default=None, metavar="DATE",
              help="Only entries published before this date (YYYY-MM-DD, UTC).")
@click.option("--fetch-limit", type=int, default=100, show_default=True,
              help="Max entries to fetch from the API per feed.")
@click.option("--max-results", type=int, default=None,
              help="Cap the number of results printed after keyword filtering.")
@click.option("--sort", "sort_fields",
              type=click.Choice(["date", "title", "url"]), multiple=True,
              help="Sort fields, ascending (repeatable). Default: date then title.")
@click.option("--format", "fmt",
              type=click.Choice(["text", "markdown", "csv", "tsv", "xml"]),
              default="text", show_default=True, help="Output format.")
@click.option("--any-keyword", "match_any", is_flag=True, default=False,
              help="Match any keyword (default: all keywords must match).")
def cmd_search(
    keywords: tuple[str, ...],
    feed_ids: tuple[int, ...],
    category_ids: tuple[int, ...],
    status: str,
    starred: bool,
    after_date: Optional[str],
    before_date: Optional[str],
    fetch_limit: int,
    max_results: Optional[int],
    sort_fields: tuple[str, ...],
    fmt: str,
    match_any: bool,
) -> None:
    """Search entry titles for KEYWORD(s)."""
    client = _make_client()

    after = _parse_date(after_date, end_of_day=False)
    before = _parse_date(before_date, end_of_day=True)
    api_status = None if status == "all" else status

    try:
        entries = client.get_entries(
            feed_ids=list(feed_ids) or None,
            category_ids=list(category_ids) or None,
            status=api_status,
            starred=starred or None,
            after=after,
            before=before,
            limit=fetch_limit,
        )
    except MinifluxAPIError as e:
        raise click.ClickException(str(e))

    results = filter_by_keywords(entries, list(keywords), match_any=match_any)

    active_sort = sort_fields or ("date", "title")
    _SORT_KEY = {
        "date": lambda e: e.published_at,
        "title": lambda e: e.title.lower(),
        "url": lambda e: e.url.lower(),
    }
    results = sorted(
        results,
        key=lambda e: tuple(_SORT_KEY[f](e) for f in active_sort),
    )

    if max_results is not None:
        results = results[:max_results]

    if not results:
        click.echo("No results found.", err=True)
        return

    _print_results(results, fmt)
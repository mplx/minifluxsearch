# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

import csv
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

from minifluxsearch.cli import _entry_date, _print_results
from minifluxsearch.models import Entry


# -- helpers -------------------------------------------------------------------

def _entry(title: str = "Test Entry",
           url: str = "https://example.com/post",
           date: datetime = datetime(2026, 4, 10, tzinfo=timezone.utc),
           **kw) -> Entry:
    return Entry(
        id=1, title=title, url=url,
        status="unread", starred=False,
        published_at=date,
        feed_id=1, feed_title="Feed",
        **kw,
    )


# -- _entry_date ---------------------------------------------------------------

def test_entry_date_normal():
    e = _entry(date=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc))
    assert _entry_date(e) == "2026-04-10"


def test_entry_date_zero_year_returns_empty():
    e = _entry(date=datetime.min.replace(tzinfo=timezone.utc))
    assert _entry_date(e) == ""


# -- text format ---------------------------------------------------------------

def test_text_format(capsys):
    _print_results([_entry("My Title", "https://example.com/post")], "text")
    out = capsys.readouterr().out
    assert "My Title" in out
    assert "https://example.com/post" in out
    assert "2026-04-10" in out


def test_text_format_no_date_for_min_date(capsys):
    _print_results([_entry(date=datetime.min.replace(tzinfo=timezone.utc))], "text")
    out = capsys.readouterr().out
    assert "[" not in out


# -- markdown format -----------------------------------------------------------

def test_markdown_format_has_header(capsys):
    _print_results([_entry()], "markdown")
    out = capsys.readouterr().out
    assert "| Date" in out
    assert "| Title" in out
    assert "| URL" in out


def test_markdown_format_has_separator(capsys):
    _print_results([_entry()], "markdown")
    out = capsys.readouterr().out
    assert "|---" in out or "|--" in out


def test_markdown_format_contains_entry(capsys):
    _print_results([_entry("Rust async")], "markdown")
    out = capsys.readouterr().out
    assert "Rust async" in out


# -- csv format ----------------------------------------------------------------

def test_csv_has_header(capsys):
    _print_results([_entry()], "csv")
    out = capsys.readouterr().out
    reader = csv.reader(io.StringIO(out))
    header = next(reader)
    assert header == ["date", "title", "url"]


def test_csv_has_data_row(capsys):
    _print_results([_entry("My Title", "https://example.com/post")], "csv")
    out = capsys.readouterr().out
    reader = csv.reader(io.StringIO(out))
    next(reader)  # skip header
    row = next(reader)
    assert row[0] == "2026-04-10"
    assert row[1] == "My Title"
    assert row[2] == "https://example.com/post"


def test_csv_quotes_commas_in_title(capsys):
    _print_results([_entry("Title, with comma")], "csv")
    out = capsys.readouterr().out
    reader = csv.reader(io.StringIO(out))
    next(reader)
    row = next(reader)
    assert row[1] == "Title, with comma"


# -- tsv format ----------------------------------------------------------------

def test_tsv_delimiter_is_tab(capsys):
    _print_results([_entry()], "tsv")
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert "\t" in lines[0]
    assert lines[0].split("\t") == ["date", "title", "url"]


# -- xml format ----------------------------------------------------------------

def test_xml_root_element(capsys):
    _print_results([_entry()], "xml")
    out = capsys.readouterr().out
    root = ET.fromstring(out)
    assert root.tag == "entries"


def test_xml_single_entry_structure(capsys):
    _print_results([_entry("Python News", "https://example.com/python")], "xml")
    out = capsys.readouterr().out
    root = ET.fromstring(out)
    assert len(root) == 1
    entry = root[0]
    assert entry.tag == "entry"
    assert entry.find("title").text == "Python News"
    assert entry.find("url").text == "https://example.com/python"
    assert entry.find("date").text == "2026-04-10"


def test_xml_multiple_entries(capsys):
    entries = [_entry("A"), _entry("B"), _entry("C")]
    _print_results(entries, "xml")
    out = capsys.readouterr().out
    root = ET.fromstring(out)
    assert len(root) == 3
    titles = [el.find("title").text for el in root]
    assert titles == ["A", "B", "C"]


def test_xml_special_chars_escaped(capsys):
    _print_results([_entry("A & B <test>")], "xml")
    out = capsys.readouterr().out
    root = ET.fromstring(out)  # would raise if not valid XML
    assert root[0].find("title").text == "A & B <test>"


def test_xml_empty_date_for_min_date(capsys):
    _print_results([_entry(date=datetime.min.replace(tzinfo=timezone.utc))], "xml")
    out = capsys.readouterr().out
    root = ET.fromstring(out)
    # ET serialises empty string as <date /> which round-trips back as None
    assert root[0].find("date").text in (None, "")

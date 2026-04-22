# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from datetime import datetime, timezone

import pytest

from minifluxsearch.models import Entry
from minifluxsearch.search import filter_by_keywords


# -- helpers -------------------------------------------------------------------

def _entry(title: str, **kw) -> Entry:
    return Entry(
        id=1, title=title, url="https://example.com",
        status="unread", starred=False,
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        feed_id=1, feed_title="Feed",
        **kw,
    )

ENTRIES = [
    _entry("Python 3.12 release notes"),
    _entry("Rust async deep dive"),
    _entry("Python security advisory"),
    _entry("Go generics tutorial"),
    _entry("Einhell 18V drill review"),
]


# -- empty keywords ------------------------------------------------------------

def test_empty_keywords_returns_all():
    assert filter_by_keywords(ENTRIES, []) == ENTRIES


def test_empty_entries_returns_empty():
    assert filter_by_keywords([], ["python"]) == []


# -- AND logic (default) -------------------------------------------------------

def test_single_keyword_match():
    result = filter_by_keywords(ENTRIES, ["python"])
    assert len(result) == 2
    assert all("python" in e.title.lower() for e in result)


def test_single_keyword_no_match():
    assert filter_by_keywords(ENTRIES, ["java"]) == []


def test_multiple_keywords_all_must_match():
    result = filter_by_keywords(ENTRIES, ["python", "security"])
    assert len(result) == 1
    assert result[0].title == "Python security advisory"


def test_multiple_keywords_partial_match_excluded():
    result = filter_by_keywords(ENTRIES, ["python", "tutorial"])
    assert result == []


# -- OR logic -----------------------------------------------------------------

def test_any_keyword_matches_either():
    result = filter_by_keywords(ENTRIES, ["python", "rust"], match_any=True)
    assert len(result) == 3


def test_any_keyword_no_match():
    result = filter_by_keywords(ENTRIES, ["java", "kotlin"], match_any=True)
    assert result == []


# -- case insensitivity --------------------------------------------------------

def test_case_insensitive_lower():
    assert len(filter_by_keywords(ENTRIES, ["python"])) == 2


def test_case_insensitive_upper():
    assert len(filter_by_keywords(ENTRIES, ["PYTHON"])) == 2


def test_case_insensitive_mixed():
    assert len(filter_by_keywords(ENTRIES, ["PyThOn"])) == 2


# -- substring matching --------------------------------------------------------

def test_substring_match():
    result = filter_by_keywords(ENTRIES, ["einhell"])
    assert len(result) == 1
    assert result[0].title == "Einhell 18V drill review"


def test_partial_word_matches():
    result = filter_by_keywords(ENTRIES, ["relea"])
    assert len(result) == 1
    assert "release" in result[0].title.lower()
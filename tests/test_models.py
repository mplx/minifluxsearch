# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from datetime import datetime, timezone

import pytest

from minifluxsearch.models import (
    Category,
    Entry,
    Feed,
    category_from_dict,
    entry_from_dict,
    feed_from_dict,
)


# -- helpers -------------------------------------------------------------------

def _feed_dict(**kw) -> dict:
    return {
        "id": 1, "title": "My Feed", "site_url": "https://site.example.com",
        "feed_url": "https://site.example.com/feed.xml", "disabled": False,
        **kw,
    }

def _entry_dict(**kw) -> dict:
    return {
        "id": 10, "title": "My Entry", "url": "https://site.example.com/post",
        "status": "unread", "starred": False,
        "published_at": "2026-04-10T10:00:00Z",
        "feed_id": 1, "feed": {"id": 1, "title": "My Feed"}, "tags": [],
        **kw,
    }


# -- category_from_dict --------------------------------------------------------

def test_category_from_dict():
    cat = category_from_dict({"id": 5, "title": "Tech"})
    assert cat.id == 5
    assert cat.title == "Tech"


# -- feed_from_dict ------------------------------------------------------------

def test_feed_from_dict_basic():
    feed = feed_from_dict(_feed_dict())
    assert feed.id == 1
    assert feed.title == "My Feed"
    assert feed.site_url == "https://site.example.com"
    assert feed.feed_url == "https://site.example.com/feed.xml"
    assert feed.disabled is False
    assert feed.category is None


def test_feed_from_dict_with_category():
    feed = feed_from_dict(_feed_dict(category={"id": 3, "title": "Tech"}))
    assert feed.category is not None
    assert feed.category.id == 3
    assert feed.category.title == "Tech"


def test_feed_from_dict_disabled():
    feed = feed_from_dict(_feed_dict(disabled=True))
    assert feed.disabled is True


def test_feed_from_dict_missing_optional_fields():
    feed = feed_from_dict({"id": 2, "title": "Minimal"})
    assert feed.site_url == ""
    assert feed.feed_url == ""
    assert feed.category is None


# -- entry_from_dict -----------------------------------------------------------

def test_entry_from_dict_basic():
    entry = entry_from_dict(_entry_dict())
    assert entry.id == 10
    assert entry.title == "My Entry"
    assert entry.url == "https://site.example.com/post"
    assert entry.status == "unread"
    assert entry.starred is False
    assert entry.feed_id == 1
    assert entry.feed_title == "My Feed"
    assert entry.tags == []


def test_entry_from_dict_published_at_parsed():
    entry = entry_from_dict(_entry_dict(published_at="2026-04-10T10:00:00Z"))
    assert entry.published_at == datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc)


def test_entry_from_dict_zero_date_becomes_min():
    entry = entry_from_dict(_entry_dict(published_at="0001-01-01T00:00:00Z"))
    assert entry.published_at == datetime.min.replace(tzinfo=timezone.utc)


def test_entry_from_dict_bad_date_becomes_min():
    entry = entry_from_dict(_entry_dict(published_at="not-a-date"))
    assert entry.published_at == datetime.min.replace(tzinfo=timezone.utc)


def test_entry_from_dict_starred():
    entry = entry_from_dict(_entry_dict(starred=True))
    assert entry.starred is True


def test_entry_from_dict_tags():
    entry = entry_from_dict(_entry_dict(tags=["python", "news"]))
    assert entry.tags == ["python", "news"]


def test_entry_from_dict_null_tags_defaults_to_empty():
    entry = entry_from_dict(_entry_dict(tags=None))
    assert entry.tags == []


def test_entry_from_dict_feed_id_fallback_from_nested_feed():
    d = _entry_dict()
    del d["feed_id"]
    entry = entry_from_dict(d)
    assert entry.feed_id == 1  # taken from d["feed"]["id"]
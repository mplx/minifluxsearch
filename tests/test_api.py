# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest
import requests

import minifluxsearch.api as api_module
from minifluxsearch.api import MinifluxAPIError, MinifluxClient
from minifluxsearch.config import Config


# -- helpers -------------------------------------------------------------------

BASE = "https://miniflux.example.com"

@pytest.fixture
def client():
    return MinifluxClient(Config(base_url=BASE, api_key="test-key"))


def _resp(data, status=200):
    m = MagicMock()
    m.ok = status < 400
    m.status_code = status
    m.json.return_value = data
    m.text = ""
    return m


def _feed_dict(id=1, title="Feed", disabled=False):
    return {
        "id": id, "title": title, "site_url": "https://site.example.com",
        "feed_url": "https://site.example.com/feed.xml",
        "disabled": disabled, "category": None,
    }


def _entry_dict(id=1, status="unread", starred=False):
    return {
        "id": id, "title": f"Entry {id}", "url": f"https://example.com/{id}",
        "status": status, "starred": starred,
        "published_at": "2026-04-10T10:00:00Z",
        "feed_id": 1, "feed": {"id": 1, "title": "Feed"}, "tags": [],
    }


def _entries_resp(entries, total=None):
    return {"total": total or len(entries), "entries": entries}


# -- auth ----------------------------------------------------------------------

def test_auth_header_set(client):
    assert client._session.headers["X-Auth-Token"] == "test-key"


# -- get_categories ------------------------------------------------------------

def test_get_categories(client):
    client._session.get = MagicMock(return_value=_resp(
        [{"id": 1, "title": "Tech"}, {"id": 2, "title": "News"}]
    ))
    cats = client.get_categories()
    assert len(cats) == 2
    assert cats[0].title == "Tech"
    client._session.get.assert_called_once_with(
        f"{BASE}/v1/categories", params={}, timeout=30
    )


# -- get_feeds -----------------------------------------------------------------

def test_get_feeds(client):
    client._session.get = MagicMock(return_value=_resp(
        [_feed_dict(id=1), _feed_dict(id=2)]
    ))
    feeds = client.get_feeds()
    assert len(feeds) == 2
    assert feeds[0].id == 1


# -- get_entries: params -------------------------------------------------------

def test_get_entries_no_filters_hits_global_endpoint(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(limit=10)
    url = client._session.get.call_args[0][0]
    assert url == f"{BASE}/v1/entries"


def test_get_entries_uses_published_after_not_after(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    after = datetime(2026, 4, 1, tzinfo=timezone.utc)
    client.get_entries(after=after, limit=10)
    params = client._session.get.call_args[1]["params"]
    assert "published_after" in params
    assert "after" not in params
    assert params["published_after"] == int(after.timestamp())


def test_get_entries_uses_published_before_not_before(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    before = datetime(2026, 4, 30, tzinfo=timezone.utc)
    client.get_entries(before=before, limit=10)
    params = client._session.get.call_args[1]["params"]
    assert "published_before" in params
    assert "before" not in params


def test_get_entries_status_param(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(status="unread", limit=10)
    params = client._session.get.call_args[1]["params"]
    assert params["status"] == "unread"


def test_get_entries_no_status_param_when_none(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(status=None, limit=10)
    params = client._session.get.call_args[1]["params"]
    assert "status" not in params


def test_get_entries_starred_param(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(starred=True, limit=10)
    params = client._session.get.call_args[1]["params"]
    assert params["starred"] == "true"


# -- get_entries: routing ------------------------------------------------------

def test_get_entries_single_feed_id(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(feed_ids=[42], limit=10)
    url = client._session.get.call_args[0][0]
    assert url == f"{BASE}/v1/feeds/42/entries"


def test_get_entries_multiple_feed_ids_makes_one_call_per_feed(client):
    client._session.get = MagicMock(return_value=_resp(_entries_resp([])))
    client.get_entries(feed_ids=[1, 2, 3], limit=10)
    assert client._session.get.call_count == 3
    urls = [c[0][0] for c in client._session.get.call_args_list]
    assert f"{BASE}/v1/feeds/1/entries" in urls
    assert f"{BASE}/v1/feeds/2/entries" in urls
    assert f"{BASE}/v1/feeds/3/entries" in urls


def test_get_entries_category_resolves_to_feeds(client):
    feeds_resp = [_feed_dict(id=10), _feed_dict(id=20)]
    entries_resp = _entries_resp([])

    client._session.get = MagicMock(side_effect=[
        _resp(feeds_resp),   # GET /v1/categories/5/feeds
        _resp(entries_resp), # GET /v1/feeds/10/entries
        _resp(entries_resp), # GET /v1/feeds/20/entries
    ])
    client.get_entries(category_ids=[5], limit=10)

    urls = [c[0][0] for c in client._session.get.call_args_list]
    assert f"{BASE}/v1/categories/5/feeds" in urls
    assert f"{BASE}/v1/feeds/10/entries" in urls
    assert f"{BASE}/v1/feeds/20/entries" in urls
    assert f"{BASE}/v1/categories/5/entries" not in urls


# -- get_entries: results ------------------------------------------------------

def test_get_entries_returns_entries(client):
    client._session.get = MagicMock(return_value=_resp(
        _entries_resp([_entry_dict(id=1), _entry_dict(id=2)])
    ))
    entries = client.get_entries(limit=10)
    assert len(entries) == 2
    assert entries[0].id == 1


def test_get_entries_respects_limit(client):
    all_entries = [_entry_dict(id=i) for i in range(5)]
    client._session.get = MagicMock(return_value=_resp(_entries_resp(all_entries, total=5)))
    entries = client.get_entries(limit=3)
    assert len(entries) == 3


def test_get_entries_merges_multiple_feeds(client):
    client._session.get = MagicMock(side_effect=[
        _resp(_entries_resp([_entry_dict(id=1), _entry_dict(id=2)])),
        _resp(_entries_resp([_entry_dict(id=3)])),
    ])
    entries = client.get_entries(feed_ids=[1, 2], limit=10)
    assert len(entries) == 3


# -- pagination ----------------------------------------------------------------

def test_pagination(client, monkeypatch):
    monkeypatch.setattr(api_module, "PAGE_SIZE", 2)
    page1 = _entries_resp([_entry_dict(id=1), _entry_dict(id=2)], total=3)
    page2 = _entries_resp([_entry_dict(id=3)], total=3)

    client._session.get = MagicMock(side_effect=[_resp(page1), _resp(page2)])
    entries = client.get_entries(limit=100)

    assert len(entries) == 3
    assert client._session.get.call_count == 2
    offsets = [c[1]["params"]["offset"] for c in client._session.get.call_args_list]
    assert offsets == [0, 2]


def test_pagination_stops_when_fewer_than_page_size_returned(client, monkeypatch):
    monkeypatch.setattr(api_module, "PAGE_SIZE", 5)
    # Only 3 returned (< page_size 5) → should stop after one request
    client._session.get = MagicMock(return_value=_resp(
        _entries_resp([_entry_dict(id=i) for i in range(3)], total=100)
    ))
    entries = client.get_entries(limit=100)
    assert len(entries) == 3
    assert client._session.get.call_count == 1


# -- error handling ------------------------------------------------------------

def test_api_error_on_4xx(client):
    client._session.get = MagicMock(return_value=_resp(
        {"error_message": "not found"}, status=404
    ))
    with pytest.raises(MinifluxAPIError) as exc_info:
        client.get_feeds()
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value)


def test_api_error_on_401(client):
    client._session.get = MagicMock(return_value=_resp(
        {"error_message": "unauthorized"}, status=401
    ))
    with pytest.raises(MinifluxAPIError) as exc_info:
        client.get_feeds()
    assert exc_info.value.status_code == 401


def test_network_error_raises_api_error(client):
    client._session.get = MagicMock(
        side_effect=requests.exceptions.ConnectionError("refused")
    )
    with pytest.raises(MinifluxAPIError) as exc_info:
        client.get_feeds()
    assert exc_info.value.status_code == 0


# -- update_entry_status -------------------------------------------------------

def test_update_entry_status_single(client):
    client._session.put = MagicMock(return_value=_resp({}, status=204))
    client.update_entry_status([42], "read")
    client._session.put.assert_called_once_with(
        f"{BASE}/v1/entries",
        json={"entry_ids": [42], "status": "read"},
        timeout=30,
    )


def test_update_entry_status_batch(client):
    client._session.put = MagicMock(return_value=_resp({}, status=204))
    client.update_entry_status([1, 2, 3], "unread")
    body = client._session.put.call_args[1]["json"]
    assert body["entry_ids"] == [1, 2, 3]
    assert body["status"] == "unread"


# -- toggle_entry_starred ------------------------------------------------------

def test_toggle_entry_starred(client):
    client._session.put = MagicMock(return_value=_resp({}, status=204))
    client.toggle_entry_starred(99)
    client._session.put.assert_called_once_with(
        f"{BASE}/v1/entries/99/bookmark",
        json={},
        timeout=30,
    )
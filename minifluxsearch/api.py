# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from datetime import datetime
from typing import Optional

import requests

from .config import Config
from .models import Category, Entry, Feed, category_from_dict, entry_from_dict, feed_from_dict

PAGE_SIZE = 1000


class MinifluxAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class MinifluxClient:
    def __init__(self, config: Config):
        self._base_url = config.base_url
        self._session = requests.Session()
        self._session.headers["X-Auth-Token"] = config.api_key

    def get_categories(self) -> list[Category]:
        data = self._get("/v1/categories", {})
        return [category_from_dict(c) for c in data]

    def get_feeds(self) -> list[Feed]:
        data = self._get("/v1/feeds", {})
        return [feed_from_dict(f) for f in data]

    def get_entries(
        self,
        feed_ids: Optional[list[int]] = None,
        category_ids: Optional[list[int]] = None,
        status: Optional[str] = None,
        starred: Optional[bool] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Entry]:
        params: dict = {}
        if status:
            params["status"] = status
        if starred is not None:
            params["starred"] = "true" if starred else "false"
        if after is not None:
            params["published_after"] = int(after.timestamp())
        if before is not None:
            params["published_before"] = int(before.timestamp())

        # Build list of per-feed endpoints; category_ids are resolved to their
        # feeds so that --fetch-limit applies per-feed (consistent behaviour).
        endpoints: list[str] = []
        if feed_ids:
            endpoints = [f"/v1/feeds/{fid}/entries" for fid in feed_ids]
        elif category_ids:
            resolved: list[int] = []
            for cid in category_ids:
                resolved.extend(f.id for f in self._get_feeds_in_category(cid))
            endpoints = [f"/v1/feeds/{fid}/entries" for fid in resolved]
        else:
            endpoints = ["/v1/entries"]

        if len(endpoints) == 1:
            return self._fetch_entries_paginated(endpoints[0], params, limit)

        results: list[Entry] = []
        for endpoint in endpoints:
            results.extend(self._fetch_entries_paginated(endpoint, params, limit))
        return results

    def _get_feeds_in_category(self, category_id: int) -> list[Feed]:
        data = self._get(f"/v1/categories/{category_id}/feeds", {})
        return [feed_from_dict(f) for f in data]

    def _fetch_entries_paginated(
        self, path: str, params: dict, limit: int
    ) -> list[Entry]:
        page_size = min(limit, PAGE_SIZE)
        collected: list[Entry] = []
        offset = 0

        while len(collected) < limit:
            page_params = {**params, "limit": page_size, "offset": offset}
            data = self._get(path, page_params)
            entries = data.get("entries") or []
            collected.extend(entry_from_dict(e) for e in entries)
            if len(entries) < page_size or len(collected) >= data.get("total", 0):
                break
            offset += page_size

        return collected[:limit]

    def update_entry_status(self, entry_ids: list[int], status: str) -> None:
        """Set status of one or more entries to 'read' or 'unread'."""
        self._put("/v1/entries", {"entry_ids": entry_ids, "status": status})

    def toggle_entry_starred(self, entry_id: int) -> None:
        """Toggle the starred/bookmark state of an entry."""
        self._put(f"/v1/entries/{entry_id}/bookmark", {})

    def _put(self, path: str, body: dict) -> None:
        try:
            resp = self._session.put(self._base_url + path, json=body, timeout=30)
        except requests.exceptions.RequestException as e:
            raise MinifluxAPIError(0, str(e))
        if not resp.ok:
            try:
                msg = resp.json().get("error_message", resp.text)
            except Exception:
                msg = resp.text
            raise MinifluxAPIError(resp.status_code, msg)

    def _get(self, path: str, params: dict) -> dict:
        try:
            resp = self._session.get(self._base_url + path, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            raise MinifluxAPIError(0, str(e))

        if not resp.ok:
            try:
                msg = resp.json().get("error_message", resp.text)
            except Exception:
                msg = resp.text
            raise MinifluxAPIError(resp.status_code, msg)

        return resp.json()
# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Category:
    id: int
    title: str


@dataclass
class Feed:
    id: int
    title: str
    site_url: str
    feed_url: str
    disabled: bool = False
    category: Optional[Category] = None


@dataclass
class Entry:
    id: int
    title: str
    url: str
    status: str
    starred: bool
    published_at: datetime
    feed_id: int
    feed_title: str
    tags: list[str] = field(default_factory=list)


def category_from_dict(data: dict) -> Category:
    return Category(id=data["id"], title=data["title"])


def feed_from_dict(data: dict) -> Feed:
    cat = None
    if data.get("category"):
        cat = Category(id=data["category"]["id"], title=data["category"]["title"])
    return Feed(
        id=data["id"],
        title=data["title"],
        site_url=data.get("site_url", ""),
        feed_url=data.get("feed_url", ""),
        disabled=data.get("disabled", False),
        category=cat,
    )


def entry_from_dict(data: dict) -> Entry:
    try:
        published_at = datetime.fromisoformat(
            data["published_at"].replace("Z", "+00:00")
        )
        # Miniflux uses the zero time for entries without a publish date
        if published_at.year == 1:
            published_at = datetime.min.replace(tzinfo=timezone.utc)
    except (ValueError, KeyError):
        published_at = datetime.min.replace(tzinfo=timezone.utc)

    feed = data.get("feed", {})
    return Entry(
        id=data["id"],
        title=data.get("title", ""),
        url=data.get("url", ""),
        status=data.get("status", ""),
        starred=data.get("starred", False),
        published_at=published_at,
        feed_id=data.get("feed_id", feed.get("id", 0)),
        feed_title=feed.get("title", ""),
        tags=data.get("tags") or [],
    )
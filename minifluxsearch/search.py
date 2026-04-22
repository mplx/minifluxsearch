# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

from .models import Entry


def filter_by_keywords(
    entries: list[Entry],
    keywords: list[str],
    match_any: bool = False,
) -> list[Entry]:
    if not keywords:
        return entries

    lowered = [kw.lower() for kw in keywords]

    def matches(entry: Entry) -> bool:
        title = entry.title.lower()
        if match_any:
            return any(kw in title for kw in lowered)
        return all(kw in title for kw in lowered)

    return [e for e in entries if matches(e)]
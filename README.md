# minifluxsearch

CLI and GUI tool to search [Miniflux](https://miniflux.app) v2 RSS entries by keyword.

## Installation

### Arch Linux

A `PKGBUILD` is included. Install the AUR dependency first, then build:

```bash
yay -S python-tkcalendar   # or your preferred AUR helper
makepkg -si
```

### Other / development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Requires Python ≥ 3.11.

## Configuration

Either set environment variables:

```bash
export MINIFLUX_URL="https://your-miniflux-instance"
export MINIFLUX_API_KEY="your-api-key"
```

or create the config file manually:

| Platform | Path |
|----------|------|
| Linux / macOS | `~/.config/minifluxsearch/config.toml` |
| Windows | `%APPDATA%\minifluxsearch\config.toml` |

```toml
[miniflux]
url = "https://your-miniflux-instance"
api_key = "your-api-key"
```

Generate an API key in Miniflux under *Settings → API Keys*. Later you can use the **Config** button in the GUI.

## GUI

```bash
minifluxsearch-gui
```

- Left panel: tabbed Feeds / Categories listbox - click to select, Shift+click for range, Ctrl+click to toggle, Ctrl+A for all
- Filter controls: status, starred, date pickers (with enable checkbox), fetch limit, max results
- Results table: Date / ★ / Title / URL columns - click headers to sort
- Keywords field: dropdown with last 10 searches; leave empty to list all matching entries
- **Double-click** or **Enter**: open in browser, mark as read
- **Ctrl+A**: select all results
- **r**: toggle read/unread for selected entries
- **s**: toggle starred for selected entries
- **k**: focus the keyword input field
- **Right-click**: context menu for read/unread, star/unstar, open - acts on all selected entries
- **Mark as read** / **Mark as unread** buttons: mark all selected entries (or all results if none selected)
- **Config** button: edit Miniflux URL, API key, and UI theme
- Unread entries shown in bold; starred entries show ★
- Filter state, keyword history, theme, and window size/position are saved and restored on next launch

### Themes

The Config dialog offers three themes:

- **System** - plain tkinter default
- **Forest Light** (default) - clean light theme
- **Forest Dark** - dark variant

Forest theme © 2021 [rdbende](https://github.com/rdbende/Forest-ttk-theme), MIT licensed.

## CLI

### List categories and feeds

```bash
minifluxsearch categories        # show category IDs and titles
minifluxsearch feeds             # show feed IDs, titles, and categories
```

Feeds with "Do not refresh this feed" enabled are not shown.

### Search

```
minifluxsearch search [OPTIONS] [KEYWORD...]
```

```
Options:
  --feed-id INTEGER                 Fetch from this feed (repeatable)
  --category-id INTEGER             Fetch from this category (repeatable)
  --status [read|unread|all]        Filter by read status  [default: all]
  --starred                         Only starred entries
  --after DATE                      Published on or after YYYY-MM-DD (UTC)
  --before DATE                     Published on or before YYYY-MM-DD (UTC)
  --fetch-limit INTEGER             Max entries fetched per feed  [default: 1000]
  --max-results INTEGER             Max results printed after filtering
  --sort [date|title|url]           Sort field, ascending (repeatable)  [default: date title]
  --format [text|markdown|csv|tsv|xml]  Output format  [default: text]
  --any-keyword                     Match any keyword (default: all must match)
```

Without `--feed-id` or `--category-id`, all feeds are searched. `--fetch-limit` applies per feed; `--max-results` caps the final printed output. Omitting keywords lists all matching entries.

### Examples

```bash
# Search all feeds for "python"
minifluxsearch search python

# List all unread entries in two feeds from the last 30 days
minifluxsearch search --feed-id 12 --feed-id 34 --status unread --after 2026-03-22

# Search a category, match any keyword, markdown output
minifluxsearch search python \
  --category-id 13 --any-keyword \
  --after 2026-04-01 --format markdown

# Export to CSV
minifluxsearch search python --format csv > results.csv

# Daily email report for "Python" articles published since yesterday (crontab)
# cron mails stdout to the local user when the command produces output
0 7 * * * minifluxsearch search Python --after $(date -d yesterday +\%Y-\%m-\%d) --format csv
```

### Output formats

**text** (default)
```
[2026-04-10] Python News
  https://example.com/python-news
```

**markdown** - aligned table:
```
| Date       | Title                  | URL                             |
|------------|------------------------|---------------------------------|
| 2026-04-10 | Python News April 2026 | https://example.com/python-news |
```

**csv / tsv** - header row + data rows, properly quoted.

**xml**:
```xml
<entries>
  <entry>
    <date>2026-04-10</date>
    <title>Python News April 2026</title>
    <url>https://example.com/python-news</url>
  </entry>
</entries>
```

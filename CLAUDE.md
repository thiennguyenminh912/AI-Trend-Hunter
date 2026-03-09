# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Trend-Hunter is a single-file Python automation tool (`main.py`) that scrapes GitHub Trending, Hacker News, and Reddit RSS feeds for AI & engineering trends, then sends a Telegram digest. It runs daily via GitHub Actions.

## Common Commands

```bash
# Create and activate a virtual environment (required on macOS with Homebrew Python)
python3 -m venv venv
source venv/bin/activate   # run this each new terminal session

# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env with TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
cp .env.example .env   # fill in your values
python main.py

# Run without sending Telegram (quick smoke test)
# Comment out the send_telegram() call in main() temporarily, or:
TELEGRAM_TOKEN=x TELEGRAM_CHAT_ID=x python main.py  # will exit(1) on send
```

## Architecture

Everything lives in `main.py` with these logical sections:

1. **Config block** — all tuneable constants: `KEYWORDS`, `VIBE_KEYWORDS`, URL lists, score thresholds. Change filters here, not in function bodies.

2. **Scrapers** (three independent functions):
   - `scrape_github_trending()` — BeautifulSoup scrape of `github.com/trending/{lang}?since=daily`. Filters by `KEYWORDS`.
   - `fetch_hn_stories()` — Firebase REST API, filters by score ≥ `HN_MIN_SCORE` + keyword match or `Show HN`/`Launch HN`.
   - `fetch_reddit_posts()` — `feedparser` RSS, excludes titles matching `REDDIT_EXCLUDE_KEYWORDS`.

3. **Vibe scoring** (`is_vibe()` / `vibe_prefix()`) — matches `VIBE_KEYWORDS` and prepends 🔥. Applied at format time, not at scrape time.

4. **Formatting** (`format_item()`, `build_message()`) — groups items by `item["source"]` key, outputs Markdown for Telegram.

5. **Telegram sender** (`send_telegram()`) — chunks at 4000 chars to stay under the 4096-char API limit. Reads credentials from env.

Each item is a plain `dict` with keys: `source`, `title`, `url`, `description`, `meta`.

## GitHub Actions

`.github/workflows/daily-trend.yml` triggers at `0 1 * * *` (08:00 ICT). Requires two repository secrets: `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`. The `workflow_dispatch` trigger allows manual runs from the GitHub UI.

## Adding a New Source

1. Write a `fetch_xxx() -> list[dict]` function returning dicts with the five standard keys.
2. Call it in `main()` and `extend` the `all_items` list.
3. No changes needed to formatting or sending logic.

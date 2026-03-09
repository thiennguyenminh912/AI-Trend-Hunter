# AI-Trend-Hunter

A free, automated daily digest of AI & engineering trends sent to your Telegram channel — powered by GitHub Actions and Google Gemini.

Every day it scrapes **GitHub Trending**, **GitHub Topics**, **Reddit**, and **Dev.to**, then uses Gemini to write two smart Telegram messages:

- **Message 1 — Executive Brief**: Top GitHub trending repos + one key insight (in Vietnamese)
- **Message 2 — Deep Dive Catalog**: Niche topics (MCP servers, AI agents, Vibe Coding, browser automation, etc.)

---

## How It Works

```
GitHub Trending ──┐
GitHub Topics   ──┼──► Gemini AI ──► Telegram (2 messages/day)
Reddit RSS      ──┤
Dev.to RSS      ──┘
```

1. **Scrapers** collect raw data from all sources
2. **Gemini waterfall** (Pro → Flash → Lite) generates summaries — falls back to plain text if all fail
3. **Telegram sender** chunks messages to stay under the 4096-char limit

---

## Fork & Run It Yourself

### Step 1 — Fork the repo

Click **Fork** at the top of this page. That's it — the workflow file comes with it.

### Step 2 — Get your credentials

You need three things:

| Secret | How to get it |
|--------|--------------|
| `TELEGRAM_TOKEN` | Create a bot via [@BotFather](https://t.me/BotFather) on Telegram, copy the token |
| `TELEGRAM_CHAT_ID` | Add your bot to a channel/group, then check `https://api.telegram.org/bot<TOKEN>/getUpdates` for the `chat.id` |
| `GEMINI_API_KEY` | Get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey) |

### Step 3 — Add secrets to your fork

In your forked repo:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add each of the three secrets above

### Step 4 — Enable Actions

GitHub may disable Actions on forks by default:

1. Go to the **Actions** tab in your fork
2. Click **I understand my workflows, go ahead and enable them**

### Step 5 — Test it

Trigger a manual run to confirm everything works:

1. Go to **Actions** → **Daily AI Trend Digest**
2. Click **Run workflow** → **Run workflow**

Check your Telegram — you should receive two messages within ~2 minutes.

---

## Schedule

The workflow runs automatically (Vietnam time, ICT = UTC+7):

| Time | Cron (UTC) |
|------|-----------|
| 08:00 AM | `0 1 * * *` |
| 07:00 PM | `0 12 * * *` |

To change the schedule, edit `.github/workflows/daily-trend.yml` and update the `cron` values.

---

## Run Locally

```bash
# Clone and set up
git clone https://github.com/YOUR_USERNAME/AI-Trend-Hunter.git
cd AI-Trend-Hunter

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env and fill in your TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY

# Run
python main.py
```

---

## Customize

All tuneable settings are at the top of `main.py`:

| Constant | What it controls |
|----------|-----------------|
| `GITHUB_TOPICS` | GitHub topic pages to scrape (e.g. `mcp-server`, `ai-agent`) |
| `GITHUB_TRENDING_URLS` | Languages to watch on GitHub Trending |
| `REDDIT_RSS_URLS` | Subreddits to follow |
| `DEVTO_RSS_URLS` | Dev.to tags to follow |
| `COMMUNITY_KEEP_KEYWORDS` | Only keep Reddit/Dev.to posts containing these words |
| `COMMUNITY_EXCLUDE_KEYWORDS` | Drop posts with these words (help requests, etc.) |
| `GEMINI_MODELS` | Model waterfall order (change to prefer Flash for lower cost) |

To add a new source, write a `fetch_xxx() -> list[dict]` function returning dicts with keys `source`, `title`, `url`, `description`, `meta`, then call it in `main()`.

---

## Tech Stack

- **Python 3.11** — single-file script (`main.py`)
- **BeautifulSoup** — GitHub scraping
- **feedparser** — Reddit & Dev.to RSS
- **google-generativeai** — Gemini API
- **GitHub Actions** — free daily scheduler (2,000 min/month free)

---

## License

MIT — fork it, modify it, make it yours.

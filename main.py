"""
AI-Trend-Hunter: Dual-Mode Reporting
- Message 1: Executive Summary — Headline + GitHub Trending top 3-5 + daily insight
- Message 2: Detailed Catalog — Topic deep-dive (MCP, Agents, Vibe Coding, etc.)
Sources: GitHub Trending, GitHub Topics (10/topic), Reddit, Dev.to
Analysis: Gemini waterfall (pro → flash → lite)
"""

import os
import re
import sys
import time
import logging
import requests
import feedparser
import google.generativeai as genai
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

GITHUB_TRENDING_URLS = [
    ("https://github.com/trending?since=daily", "TRENDING-GLOBAL"),
    ("https://github.com/trending/python?since=daily", "TRENDING-PYTHON"),
    ("https://github.com/trending/typescript?since=daily", "TRENDING-TS"),
]

GITHUB_TOPICS = [
    "mcp-server",
    "cursor-rules",
    "ai-agent",
    "kanban",
    "generative-ui",
    "browser-use",
    "antigravity",
    "open-source-alternatives",
]
GITHUB_REPOS_PER_TOPIC = 10

REDDIT_RSS_URLS = [
    "https://www.reddit.com/r/ClaudeAI/top/.rss?t=week",
    "https://www.reddit.com/r/Cursor/top/.rss?t=week",
    "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day",
    "https://www.reddit.com/r/OpenAI/top/.rss?t=day",
]

DEVTO_RSS_URLS = [
    "https://dev.to/feed/tag/ai",
    "https://dev.to/feed/tag/productivity",
]

COMMUNITY_KEEP_KEYWORDS = [
    "showcase", "guide", "workflow", "trick", "tip", "built",
    "release", "launch", "how i", "show", "made", "tool",
]
COMMUNITY_EXCLUDE_KEYWORDS = [
    "help me", "please help", "beginner", "tutorial for",
    "what is", "explain", "question:", "[q]",
]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SUMMARY_PROMPT = """\
You are a CTO writing a Telegram message. Read this list of tech trends and write a 30-second TL;DR.

RULES — Telegram HTML only. Allowed tags: <b>, <i>, <a href="...">. No Markdown, no <ul><li><br>.
Use • for bullets. Write in Vietnamese. Be urgent, high-level, strategic.

Items tagged [TRENDING-GLOBAL], [TRENDING-PYTHON], [TRENDING-TS] are from GitHub Trending — use them for the trending section.

OUTPUT FORMAT (use exactly these 3 sections, no more):

<b>🔥 TIÊU ĐIỂM</b>
[The single most important AI/Tech news or repo today — across ALL sources. 1-2 sentences. Name the specific tool.]

<b>🚀 TOP GITHUB TRENDING</b>
Pick the 3-5 most interesting repos from [TRENDING-*] items only. Format each as:
• <b><a href="URL">owner/repo</a></b> ⭐Stars — <i>Mô tả ngắn bằng tiếng Việt</i>

<b>💡 INSIGHT NGẮN</b>
<i>[One sharp 1-sentence takeaway for the day. What signal should a Senior Dev act on?]</i>

RAW DATA:
{raw_data}\
"""

DETAIL_PROMPT = """\
You are a Senior Engineer & Librarian. Organize this raw data into a structured deep-dive catalog for Telegram.
Focus on the niche topic hunters: MCP servers, Cursor rules, AI agents, Vibe Coding, browser automation.
Do NOT repeat GitHub Trending repos unless they are directly relevant to one of these niche topics.

RULES — Telegram HTML only. Allowed tags: <b>, <i>, <a href="...">, <code>. No Markdown, no <ul><li><br>.
Use • for bullets. Write descriptions in Vietnamese. Be dense and technical — do NOT over-summarize.
Include as many relevant items as possible from [GitHub #topic] and [Reddit/Dev.to] sources.

OUTPUT FORMAT — use exactly these section headers, skip a section only if truly empty:

<b>🎨 Vibe Coding & UI</b>
• <b><a href="URL">repo/tool name</a></b> — <i>Mô tả kỹ thuật ngắn.</i> <code>#tag1 #tag2</code>

<b>🧠 Agents & Brains</b>
• <b><a href="URL">repo/tool name</a></b> — <i>Mô tả kỹ thuật ngắn.</i> <code>#tag1 #tag2</code>

<b>🔌 MCP & Integrations</b>
• <b><a href="URL">repo/tool name</a></b> — <i>Mô tả kỹ thuật ngắn.</i> <code>#tag1 #tag2</code>

<b>🆕 Python / Backend / OSS</b>
• <b><a href="URL">repo/tool name</a></b> — <i>Mô tả kỹ thuật ngắn.</i> <code>#tag1 #tag2</code>

RAW DATA:
{raw_data}\
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def contains_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in keywords)


# ---------------------------------------------------------------------------
# Hunters
# ---------------------------------------------------------------------------


def scrape_github_topics() -> list[dict]:
    """Fetch top GITHUB_REPOS_PER_TOPIC recently-updated repos per topic."""
    results = []
    for topic in GITHUB_TOPICS:
        url = f"https://github.com/topics/{topic}?o=desc&s=updated"
        log.info("GitHub topic: %s", topic)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("GitHub topic fetch failed (%s): %s", topic, exc)
            time.sleep(1)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.border")
        count = 0
        for card in cards:
            if count >= GITHUB_REPOS_PER_TOPIC:
                break
            name_tag = card.select_one("h3 a:last-child")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            repo_url = "https://github.com" + name_tag["href"].strip()

            desc_tag = card.select_one("p.color-fg-muted, p[itemprop='description']")
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            # Extract language tags from card
            lang_tags = [t.get_text(strip=True) for t in card.select("a[data-ga-click*='topic']")]

            results.append({
                "source": f"GitHub #{topic}",
                "title": name,
                "url": repo_url,
                "description": description,
                "meta": " ".join(f"#{t.lower()}" for t in lang_tags[:3]) if lang_tags else f"#{topic}",
            })
            count += 1

        log.info("  → %d repos (topic: %s)", count, topic)
        time.sleep(1)

    log.info("GitHub Topics total: %d items", len(results))
    return results


def scrape_github_trending() -> list[dict]:
    """Scrape GitHub Trending pages (global, Python, TypeScript)."""
    results = []
    for url, label in GITHUB_TRENDING_URLS:
        log.info("GitHub Trending: %s", label)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("GitHub Trending fetch failed (%s): %s", label, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.select("article.Box-row"):
            name_tag = article.select_one("h2 a")
            if not name_tag:
                continue
            name = name_tag.get_text(separator="", strip=True).replace(" ", "")
            repo_url = "https://github.com" + name_tag["href"].strip()

            desc_tag = article.select_one("p")
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            stars_tag = article.select_one("a[href$='/stargazers']")
            stars = stars_tag.get_text(strip=True).replace(",", "").strip() if stars_tag else "0"

            results.append({
                "source": label,           # e.g. "TRENDING-GLOBAL"
                "title": name,
                "url": repo_url,
                "description": description,
                "meta": f"⭐ {stars}",
            })

        log.info("  → %d repos (%s)", len([r for r in results if r["source"] == label]), label)
        time.sleep(1)

    log.info("GitHub Trending total: %d items", len(results))
    return results


def fetch_community_discussions() -> list[dict]:
    """Fetch Reddit + Dev.to RSS, keeping quality showcase/guide posts."""
    results = []

    for rss_url in REDDIT_RSS_URLS:
        subreddit = rss_url.split("/r/")[1].split("/")[0]
        log.info("Reddit RSS: r/%s", subreddit)
        try:
            feed = feedparser.parse(rss_url)
        except Exception as exc:
            log.warning("Reddit RSS failed (%s): %s", rss_url, exc)
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            if not contains_any(title, COMMUNITY_KEEP_KEYWORDS):
                continue
            if contains_any(title, COMMUNITY_EXCLUDE_KEYWORDS):
                continue
            link = entry.get("link", "")
            summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:200]
            results.append({
                "source": f"Reddit r/{subreddit}",
                "title": title,
                "url": link,
                "description": summary.strip(),
                "meta": "",
            })

    for rss_url in DEVTO_RSS_URLS:
        tag = rss_url.split("/tag/")[1]
        log.info("Dev.to tag: %s", tag)
        try:
            feed = feedparser.parse(rss_url)
        except Exception as exc:
            log.warning("Dev.to RSS failed (%s): %s", rss_url, exc)
            continue

        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            if contains_any(title, COMMUNITY_EXCLUDE_KEYWORDS):
                continue
            link = entry.get("link", "")
            summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:200]
            results.append({
                "source": f"Dev.to #{tag}",
                "title": title,
                "url": link,
                "description": summary.strip(),
                "meta": "",
            })

    log.info("Community discussions total: %d items", len(results))
    return results


# ---------------------------------------------------------------------------
# Gemini — shared waterfall runner
# ---------------------------------------------------------------------------


def _call_gemini(prompt: str, label: str) -> str | None:
    """Try each model in GEMINI_MODELS; return first successful response text."""
    if not GEMINI_API_KEY:
        log.info("GEMINI_API_KEY not set — skipping %s", label)
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    for i, model_name in enumerate(GEMINI_MODELS):
        log.info("[%s] Trying %s", label, model_name)
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response.text:
                log.info("[%s] Succeeded with %s", label, model_name)
                return response.text
        except Exception as exc:
            is_last = i == len(GEMINI_MODELS) - 1
            if is_last:
                log.warning("⚠️ [%s] %s failed — all models exhausted: %s", label, model_name, exc)
            else:
                log.warning("⚠️ [%s] %s failed, trying %s... (%s)", label, model_name, GEMINI_MODELS[i + 1], exc)

    log.error("[%s] All Gemini models failed", label)
    return None


def generate_executive_summary(raw_data_list: list[str]) -> str | None:
    raw_data = "\n---\n".join(raw_data_list)
    return _call_gemini(SUMMARY_PROMPT.format(raw_data=raw_data), "Summary")


def generate_detailed_feed(raw_data_list: list[str]) -> str | None:
    raw_data = "\n---\n".join(raw_data_list)
    return _call_gemini(DETAIL_PROMPT.format(raw_data=raw_data), "Detail")


# ---------------------------------------------------------------------------
# Fallback plain formatter
# ---------------------------------------------------------------------------


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_plain_message(all_items: list[dict]) -> str:
    sections: dict[str, list[dict]] = {}
    for item in all_items:
        sections.setdefault(item["source"], []).append(item)

    lines = ["<b>🤖 AI &amp; Vibe Coding Trends — Daily Digest</b>\n"]
    for source, items in sections.items():
        lines.append(f"\n<b>📌 {esc(source)}</b>")
        lines.append("─" * 30)
        for item in items:
            lines.append(f"<b>{esc(item['title'])}</b>")
            lines.append(item["url"])
            if item["meta"]:
                lines.append(f"<code>{esc(item['meta'])}</code>")
            if item["description"]:
                lines.append(f"<i>{esc(item['description'][:150])}</i>")
            lines.append("")
    lines.append("<i>Generated by AI-Trend-Hunter</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI output cleanup
# ---------------------------------------------------------------------------

_ALLOWED_TAGS = {"b", "i", "code", "a"}


def _clean_for_telegram(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<strong>(.*?)</strong>", r"<b>\1</b>", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>", r"<i>\1</i>", text, flags=re.IGNORECASE | re.DOTALL)

    def _keep_allowed(m: re.Match) -> str:
        tag = re.match(r"</?(\w+)", m.group(0))
        return m.group(0) if (tag and tag.group(1).lower() in _ALLOWED_TAGS) else ""

    text = re.sub(r"<[^>]+>", _keep_allowed, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def _split_chunks(text: str, limit: int = 3900) -> list[str]:
    """Split text into chunks <= limit chars, breaking at paragraph then line boundaries."""
    chunks: list[str] = []
    current = ""

    def add_line(line: str, sep: str) -> str:
        nonlocal chunks
        candidate = current + (sep if current else "") + line
        if len(candidate) <= limit:
            return candidate
        # current is full — flush it, start fresh with this line
        if current:
            chunks.append(current)
        # If the line itself exceeds limit, hard-split by chars
        if len(line) > limit:
            for i in range(0, len(line), limit):
                piece = line[i:i + limit]
                if i + limit < len(line):
                    chunks.append(piece)
                else:
                    return piece
        return line

    for paragraph in text.split("\n\n"):
        # Try to add the whole paragraph first
        candidate = current + ("\n\n" if current else "") + paragraph
        if len(candidate) <= limit:
            current = candidate
        else:
            # Paragraph too large — flush current, then split paragraph by lines
            if current:
                chunks.append(current)
                current = ""
            for line in paragraph.split("\n"):
                current = add_line(line, "\n")

    if current:
        chunks.append(current)
    return chunks


def send_telegram(text: str, label: str = "") -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set")
        sys.exit(1)

    chunks = _split_chunks(text)
    for idx, chunk in enumerate(chunks, 1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(TELEGRAM_API_URL, json=payload, timeout=15)
            resp.raise_for_status()
            log.info("[%s] chunk %d/%d sent (%d chars)", label or "msg", idx, len(chunks), len(chunk))
        except requests.RequestException as exc:
            # On 400 (bad HTML), retry without parse_mode as plain text fallback
            if hasattr(exc, "response") and exc.response is not None and exc.response.status_code == 400:
                log.warning("[%s] chunk %d HTML parse error — retrying as plain text", label or "msg", idx)
                plain = re.sub(r"<[^>]+>", "", chunk)
                payload["text"] = plain
                payload.pop("parse_mode", None)
                try:
                    resp2 = requests.post(TELEGRAM_API_URL, json=payload, timeout=15)
                    resp2.raise_for_status()
                    log.info("[%s] chunk %d/%d sent as plain text (%d chars)", label or "msg", idx, len(chunks), len(plain))
                    continue
                except requests.RequestException as exc2:
                    log.error("[%s] plain text retry also failed: %s", label or "msg", exc2)
            log.error("[%s] Telegram send failed on chunk %d: %s", label or "msg", idx, exc)
            raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # ── 1. Collect ──────────────────────────────────────────────────────────
    trending_items = scrape_github_trending()
    topic_items = scrape_github_topics()
    community_items = fetch_community_discussions()

    all_items = trending_items + topic_items + community_items

    if not all_items:
        log.info("No items found — nothing to send")
        return

    log.info(
        "Collected: %d trending + %d topics + %d community = %d total",
        len(trending_items), len(topic_items), len(community_items), len(all_items),
    )

    def to_raw(item: dict) -> str:
        return (
            f"[{item['source']}] {item['title']} | {item['url']} "
            f"| {item['description'][:120]} | {item['meta']}"
        )

    # Both passes receive all data; prompts instruct each to focus differently
    raw_data_list = [to_raw(i) for i in all_items]

    # ── 2. Two-pass AI analysis ──────────────────────────────────────────────
    summary_text = generate_executive_summary(raw_data_list)
    detail_text = generate_detailed_feed(raw_data_list)

    # ── 3. Send Message 1: Executive Summary ────────────────────────────────
    if summary_text:
        msg1 = "<b>⚡ AI Trend Hunter — Daily Brief</b>\n\n" + _clean_for_telegram(summary_text)
    else:
        log.warning("Summary generation failed — sending plain fallback")
        msg1 = build_plain_message(all_items)

    try:
        send_telegram(msg1, label="Summary")
    except Exception as exc:
        log.error("Failed to send summary: %s", exc)

    # ── 4. Send Message 2: Detailed Catalog ─────────────────────────────────
    if detail_text:
        msg2 = "<b>📚 Deep Dive — Full Tech Catalog</b>\n\n" + _clean_for_telegram(detail_text)
        try:
            send_telegram(msg2, label="Detail")
        except Exception as exc:
            log.error("Failed to send detail feed: %s", exc)
    else:
        log.warning("Detail generation failed — skipping detail message")

    log.info("Done.")


if __name__ == "__main__":
    main()

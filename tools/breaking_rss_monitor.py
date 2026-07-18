#!/usr/bin/env python3
"""Publish concise, rule-based breaking alerts from public RSS and Atom feeds."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


STATE_PATH = Path("data/breaking_sent.json")
BREAKING_PAGE = Path("breaking-news.html")
PUBLIC_BASE_URL = "https://chenchao9990-creator.github.io/ai-blockchain-briefing"
LOOKBACK = timedelta(hours=3)


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    default_category: str


FEEDS = (
    Feed("BBC News World", "https://feeds.bbci.co.uk/news/world/rss.xml", "Conflict"),
    Feed("BBC News UK", "https://feeds.bbci.co.uk/news/uk/rss.xml", "US / UK Policy"),
    Feed("BBC News Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "Markets"),
    Feed("The White House", "https://www.whitehouse.gov/feed/", "US / UK Policy"),
    Feed("U.S. Department of State", "https://www.state.gov/feed/", "US / UK Policy"),
    Feed("GOV.UK", "https://www.gov.uk/search/news-and-communications.atom", "US / UK Policy"),
)

CONFLICT_WORDS = {
    "war", "military", "missile", "strike", "attack", "troops", "ceasefire", "invasion",
    "iran", "israel", "gaza", "ukraine", "russia", "hormuz", "navy", "sanctions",
}
POLICY_WORDS = {
    "white house", "executive order", "state department", "treasury", "congress", "senate",
    "law", "bill", "regulation", "policy", "tariff", "sanctions", "home office", "parliament",
    "downing street", "uk government", "gov.uk", "ministry", "cma", "bank of england",
}
AI_WORDS = {
    "artificial intelligence", "openai", "anthropic", "google", "deepmind", "microsoft",
    "meta", "nvidia", "xai", "chip", "semiconductor", "data centre", "data center",
}
CRYPTO_WORDS = {
    "bitcoin", "ethereum", "crypto", "stablecoin", "blockchain", "token", "etf", "defi",
}


def plain(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def fetch_feed(feed: Feed) -> list[dict[str, str]]:
    request = urllib.request.Request(feed.url, headers={"User-Agent": "Mozilla/5.0 breaking-news-monitor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    entries: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        entries.append({
            "title": plain(item.findtext("title")),
            "url": plain(item.findtext("link")),
            "summary": plain(item.findtext("description")),
            "published": plain(item.findtext("pubDate")),
        })
    namespace = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f".//{namespace}entry"):
        link = next((node.attrib.get("href", "") for node in entry.findall(f"{namespace}link") if node.attrib.get("rel", "alternate") == "alternate"), "")
        entries.append({
            "title": plain(entry.findtext(f"{namespace}title")),
            "url": link,
            "summary": plain(entry.findtext(f"{namespace}summary") or entry.findtext(f"{namespace}content")),
            "published": plain(entry.findtext(f"{namespace}published") or entry.findtext(f"{namespace}updated")),
        })
    return [entry for entry in entries if entry["title"] and entry["url"]]


def parse_published(value: str) -> datetime | None:
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def contains_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def classify(text: str, fallback: str) -> str | None:
    if contains_any(text, CONFLICT_WORDS):
        return "Conflict"
    if contains_any(text, CRYPTO_WORDS):
        return "Crypto"
    if contains_any(text, AI_WORDS):
        return "AI"
    if contains_any(text, POLICY_WORDS):
        return "US / UK Policy"
    return fallback if fallback == "Conflict" else None


def keywords(text: str, category: str) -> list[str]:
    vocabulary = {
        "Conflict": CONFLICT_WORDS,
        "US / UK Policy": POLICY_WORDS,
        "AI": AI_WORDS,
        "Crypto": CRYPTO_WORDS,
    }.get(category, set())
    found = [word for word in vocabulary if word in text]
    labels = [word.title() if word != "ai" else "AI" for word in found[:5]]
    return labels or [category]


def load_state() -> list[dict[str, str]]:
    if not STATE_PATH.exists():
        return []
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def alert_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def build_alert(entry: dict[str, str], feed: Feed) -> dict[str, str] | None:
    published = parse_published(entry["published"])
    if not published or published < datetime.now(timezone.utc) - LOOKBACK:
        return None
    text = f"{entry['title']} {entry['summary']}".lower()
    category = classify(text, feed.default_category)
    if not category:
        return None
    detail = entry["summary"] or entry["title"]
    return {
        "key": alert_key(entry["url"]),
        "headline": entry["title"],
        "story": detail[:900],
        "keywords": " | ".join(keywords(text, category)),
        "category": category,
        "publication": feed.name,
        "url": entry["url"],
        "published_at": published.isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def telegram_message(alert: dict[str, str]) -> str:
    return "\n\n".join([
        f"<b>BREAKING: {html.escape(alert['headline'])}</b>",
        html.escape(alert["story"]),
        f"<b>Keywords:</b> {html.escape(alert['keywords'])}",
        f"<b>Source:</b> <a href=\"{html.escape(alert['url'], quote=True)}\">{html.escape(alert['publication'])}</a>",
    ])


def send_telegram(alert: dict[str, str]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    payload = json.dumps({
        "chat_id": chat_id,
        "text": telegram_message(alert),
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": False},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def write_page(alerts: list[dict[str, str]]) -> None:
    rows = "".join(
        f'''<li><p class="category">{html.escape(item['category'])}</p><h2><a href="{html.escape(item['url'], quote=True)}">{html.escape(item['headline'])}</a></h2><p>{html.escape(item['story'])}</p><p class="keywords">Keywords: {html.escape(item['keywords'])}</p><p class="source">{html.escape(item['publication'])} · {html.escape(item['sent_at'])}</p></li>'''
        for item in reversed(alerts[-30:])
    ) or "<li><p>No breaking alerts have been published yet.</p></li>"
    BREAKING_PAGE.write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Breaking News | AI, Crypto &amp; Tech Power Briefing</title><style>
body{{margin:0;background:#f6f4ef;color:#17202a;font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:860px;margin:auto;padding:26px 16px 54px}}nav{{padding-bottom:18px;border-bottom:1px solid #ded8cc}}a{{color:#164a7c;text-underline-offset:3px}}h1{{font:clamp(2.3rem,8vw,4.5rem)/1.05 Georgia,serif;color:#164a7c;margin:28px 0 12px}}h2{{font-size:1.35rem;line-height:1.25;margin:0 0 9px}}ul{{list-style:none;padding:0;margin:26px 0;border-top:1px solid #ded8cc}}li{{padding:22px 0;border-bottom:1px solid #ded8cc}}p{{margin:0 0 10px}}.category,.keywords{{font-weight:750;color:#24765d}}.source{{color:#667085;font-size:.9rem}}</style></head>
<body><main><nav><a href="index.html">Latest briefing</a> · <a href="archive.html">Archive</a> · Breaking News</nav><header><h1>Breaking News</h1><p>Major AI, crypto, conflict and US / UK policy updates. Facts first, with keywords and source links.</p></header><ul>{rows}</ul></main></body></html>''', encoding="utf-8")


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "0") == "1"
    state = load_state()
    seen = {item.get("key") for item in state}
    candidates: list[dict[str, str]] = []
    for feed in FEEDS:
        try:
            for entry in fetch_feed(feed):
                alert = build_alert(entry, feed)
                if alert and alert["key"] not in seen:
                    candidates.append(alert)
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError) as exc:
            print(f"Skipping {feed.name}: {exc}", file=sys.stderr)
    candidates.sort(key=lambda item: item["published_at"], reverse=True)
    new_alerts = candidates[:2]
    if dry_run:
        print(json.dumps(new_alerts, ensure_ascii=False, indent=2))
        return 0
    for alert in new_alerts:
        send_telegram(alert)
        state.append(alert)
    if new_alerts:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    write_page(state)
    print(f"Published {len(new_alerts)} breaking alert(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Send the latest briefing summary to a Telegram channel."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_BASE_URL = "https://chenchao9990-creator.github.io/ai-blockchain-briefing"


@dataclass
class Briefing:
    path: Path
    title: str
    date: str
    headline: str
    overview: list[str]
    stories: list[str]
    pdf_href: str | None


class BriefingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._in_overview = False
        self._in_toc = False
        self._current_link_href: str | None = None

        self.title = ""
        self.date = ""
        self.headline = ""
        self.overview: list[str] = []
        self.stories: list[str] = []
        self.pdf_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())

        if tag == "section" and "overview" in classes:
            self._in_overview = True
        elif tag == "ol" and "toc" in classes:
            self._in_toc = True

        if tag == "p" and "kicker" in classes:
            self._start_capture("date")
        elif tag == "p" and "headline" in classes:
            self._start_capture("headline")
        elif tag == "h1" and not self.title:
            self._start_capture("title")
        elif tag == "p" and self._in_overview:
            self._start_capture("overview")
        elif tag == "a":
            href = attr.get("href")
            if href and href.endswith(".pdf") and self.pdf_href is None:
                self.pdf_href = href
            if self._in_toc:
                self._current_link_href = href
                self._start_capture("story")

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag in {"p", "h1", "a"}:
            text = " ".join("".join(self._buffer).split())
            if text:
                if self._capture == "date":
                    self.date = text.split("·")[-1].strip()
                elif self._capture == "headline":
                    self.headline = text
                elif self._capture == "title":
                    self.title = text
                elif self._capture == "overview":
                    self.overview.append(text)
                elif self._capture == "story":
                    self.stories.append(text)
            self._capture = None
            self._buffer = []
            self._current_link_href = None

        if tag == "section" and self._in_overview:
            self._in_overview = False
        elif tag == "ol" and self._in_toc:
            self._in_toc = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def _start_capture(self, name: str) -> None:
        self._capture = name
        self._buffer = []


def latest_briefing_file() -> Path:
    explicit = os.environ.get("BRIEFING_HTML")
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"BRIEFING_HTML does not exist: {path}")
        return path

    candidates = sorted(Path(".").glob("daily_ai_blockchain_briefing_*.html"))
    if candidates:
        return candidates[-1]

    fallback = Path("index.html")
    if fallback.exists():
        return fallback

    raise FileNotFoundError("No briefing HTML file found.")


def parse_briefing(path: Path) -> Briefing:
    parser = BriefingParser()
    parser.feed(path.read_text(encoding="utf-8"))

    return Briefing(
        path=path,
        title=parser.title or "Daily AI & Blockchain Briefing",
        date=parser.date or "Latest issue",
        headline=parser.headline or "Daily AI & Blockchain Briefing",
        overview=parser.overview[:2],
        stories=parser.stories[:5],
        pdf_href=parser.pdf_href,
    )


def absolute_url(base_url: str, href: str) -> str:
    base = base_url.rstrip("/")
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{base}/{href.lstrip('./')}"


def build_message(briefing: Briefing, base_url: str) -> str:
    issue_url = absolute_url(base_url, briefing.path.name)
    pdf_url = absolute_url(base_url, briefing.pdf_href) if briefing.pdf_href else None

    parts = [
        f"<b>{escape(briefing.title)}</b>",
        escape(briefing.date),
        "",
        f"<b>{escape(briefing.headline)}</b>",
        "",
    ]

    for paragraph in briefing.overview:
        parts.append(escape(paragraph))
        parts.append("")

    if briefing.stories:
        parts.append("<b>Top stories</b>")
        for index, story in enumerate(briefing.stories, start=1):
            clean_story = re.sub(r"^\s*\d+\.\s*", "", story)
            parts.append(f"{index}. {escape(clean_story)}")
        parts.append("")

    parts.append(f'<a href="{escape(issue_url, quote=True)}">Read full briefing</a>')
    if pdf_url:
        parts.append(f'<a href="{escape(pdf_url, quote=True)}">Open PDF archive</a>')

    message = "\n".join(parts).strip()
    if len(message) > 3900:
        message = message[:3860].rstrip() + "\n\nRead full briefing: " + issue_url
    return message


def send_message(token: str, chat_id: str, message: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API returned HTTP {exc.code}: {details}") from exc

    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")


def main() -> int:
    base_url = os.environ.get("PUBLIC_BASE_URL", DEFAULT_BASE_URL)
    dry_run = os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    briefing = parse_briefing(latest_briefing_file())
    message = build_message(briefing, base_url)

    if dry_run:
        print(message)
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID; skipping Telegram push.")
        return 0

    send_message(token, chat_id, message)
    print(f"Sent Telegram briefing update for {briefing.path.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

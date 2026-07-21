#!/usr/bin/env python3
"""Generate daily briefings or Telegram breaking-news alerts with OpenAI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any


SITE_TITLE = "Daily AI, Crypto & Tech Power Briefing"
SITE_NAV_TITLE = "AI, Crypto & Tech Power Briefing"
SITE_SCOPE = "AI · Crypto · Tech Power · Policy · Business"
SITE_FOOTER = "Daily AI, Crypto & Tech Power News Study Briefing"
PUBLIC_BASE_URL = "https://chenchao9990-creator.github.io/ai-blockchain-briefing"
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5"
STATE_DIR = Path("data")
BREAKING_STATE = STATE_DIR / "breaking_sent.json"

ALLOWED_NEWS_DOMAINS = [
    "reuters.com",
    "ft.com",
    "bloomberg.com",
    "cnbc.com",
    "theverge.com",
    "wsj.com",
    "techcrunch.com",
    "coindesk.com",
    "cointelegraph.com",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "microsoft.com",
    "meta.com",
    "nvidia.com",
    "apple.com",
    "aboutamazon.com",
    "x.ai",
    "tesla.com",
    "spacex.com",
    "sec.gov",
    "cftc.gov",
    "federalreserve.gov",
    "whitehouse.gov",
    "gov.uk",
    "europa.eu",
]


HTML_STYLE = """
      :root {
        color-scheme: light;
        --bg: #f6f4ef;
        --ink: #17202a;
        --muted: #667085;
        --line: #ded8cc;
        --blue: #164a7c;
        --green: #24765d;
        --soft-blue: #eaf3fb;
        --soft-green: #edf7f2;
        --soft-gold: #fff7e3;
        --shadow: 0 16px 45px rgba(38, 52, 65, 0.08);
      }
      * { box-sizing: border-box; }
      html { scroll-behavior: smooth; }
      body {
        margin: 0;
        background: linear-gradient(180deg, rgba(255, 253, 248, 0.9), rgba(246, 244, 239, 0.92)), var(--bg);
        color: var(--ink);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        font-size: 17px;
        line-height: 1.62;
      }
      a { color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 3px; }
      .page { width: min(100%, 860px); margin: 0 auto; padding: 18px 16px 44px; }
      .site-nav {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 6px 0 14px; color: var(--muted); font-size: 0.88rem; font-weight: 750;
      }
      .site-nav a { color: var(--muted); text-decoration: none; }
      .site-nav-links { display: flex; gap: 12px; white-space: nowrap; }
      .masthead { padding: 28px 0 18px; border-bottom: 1px solid var(--line); }
      .kicker { margin: 0 0 12px; color: var(--muted); font-size: 0.82rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
      h1 { margin: 0 0 8px; color: var(--blue); font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.05rem, 9vw, 4.5rem); line-height: 0.98; letter-spacing: 0; }
      .headline { margin: 14px 0 0; font-size: clamp(1.24rem, 4.8vw, 2.1rem); line-height: 1.15; font-weight: 800; color: #151d27; }
      .meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
      .pill { display: inline-flex; align-items: center; min-height: 34px; padding: 6px 11px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,0.72); color: #3f4a57; font-size: 0.86rem; font-weight: 700; text-decoration: none; }
      .overview { margin: 22px 0 18px; padding: 17px 17px 15px; border: 1px solid #cfe0ed; border-radius: 14px; background: var(--soft-blue); box-shadow: var(--shadow); }
      .overview p, .takeaway p { margin: 0 0 12px; }
      .overview p:last-child, .takeaway p:last-child { margin-bottom: 0; }
      .toc { margin: 22px 0 22px; padding: 0; list-style: none; border-top: 1px solid var(--line); }
      .toc li { border-bottom: 1px solid var(--line); }
      .toc a { display: block; padding: 12px 0; color: var(--ink); font-size: 1rem; font-weight: 750; text-decoration: none; }
      article { margin: 28px 0 0; padding: 0 0 26px; border-bottom: 1px solid var(--line); }
      h2 { margin: 0 0 14px; color: var(--blue); font-size: clamp(1.55rem, 6vw, 2.4rem); line-height: 1.12; letter-spacing: 0; }
      h3 { margin: 23px 0 7px; color: var(--green); font-size: 0.94rem; line-height: 1.28; letter-spacing: 0; text-transform: none; }
      p { margin: 0 0 13px; }
      .reference { margin: 0 0 18px; padding: 13px 14px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,0.76); font-size: 0.94rem; line-height: 1.46; overflow-wrap: anywhere; }
      .reference div + div { margin-top: 4px; }
      .label { font-weight: 800; }
      .spoken, .discussion, .takeaway { border-radius: 14px; padding: 15px 16px; }
      .spoken { background: var(--soft-gold); border: 1px solid #ead9ad; font-style: italic; }
      .discussion { background: var(--soft-blue); border: 1px solid #cfe0ed; font-weight: 780; font-style: italic; }
      .vocab { display: grid; grid-template-columns: 1fr; gap: 8px; margin: 0; padding: 0; list-style: none; }
      .vocab li { padding: 9px 10px; border: 1px solid rgba(222,216,204,0.85); border-radius: 10px; background: rgba(255,255,255,0.62); font-size: 0.96rem; line-height: 1.35; }
      .term { font-weight: 800; }
      .watch-list { margin: 7px 0 0; padding-left: 1.2rem; }
      .watch-list li { margin: 0 0 7px; padding-left: 2px; }
      .terms { margin-top: 30px; padding-top: 1px; }
      .terms h2 { font-size: 1.45rem; }
      .term-note { margin-top: -5px; color: var(--muted); font-size: 0.92rem; }
      .takeaway { margin: 32px 0 0; background: var(--soft-green); border: 1px solid #c8e2d6; }
      .footer { margin-top: 28px; color: var(--muted); font-size: 0.88rem; text-align: center; }
      .footer a { color: var(--muted); }
      @media (min-width: 720px) {
        body { font-size: 18px; }
        .page { padding: 30px 32px 58px; }
        .masthead { padding-top: 42px; }
        .overview, .reference, .spoken, .discussion, .takeaway { border-radius: 16px; }
        .vocab { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media print {
        body { background: #fff; font-size: 11pt; }
        .page { width: 100%; padding: 0; }
        .overview, .reference, .spoken, .discussion, .takeaway, .vocab li { box-shadow: none; break-inside: avoid; }
        article { break-inside: avoid; }
        a { color: #000; }
      }
"""

ARCHIVE_STYLE = """
      :root { color-scheme: light; --bg: #f6f4ef; --ink: #17202a; --muted: #667085; --line: #ded8cc; --blue: #164a7c; --green: #24765d; --soft-blue: #eaf3fb; }
      * { box-sizing: border-box; }
      body { margin: 0; background: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; font-size: 17px; line-height: 1.6; }
      a { color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 3px; }
      .page { width: min(100%, 860px); margin: 0 auto; padding: 24px 16px 48px; }
      .site-nav { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 0 18px; color: var(--muted); font-size: 0.88rem; font-weight: 750; }
      .site-nav a { color: var(--muted); text-decoration: none; }
      .site-nav-links { display: flex; gap: 12px; white-space: nowrap; }
      header { padding: 18px 0 22px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
      .kicker { margin: 0 0 10px; color: var(--muted); font-size: 0.82rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
      h1 { margin: 0; color: var(--blue); font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.2rem, 10vw, 4.4rem); line-height: 1; letter-spacing: 0; }
      .intro { margin: 18px 0 0; max-width: 42rem; color: #2d3844; }
      .archive-list { margin: 26px 0 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
      .archive-item { padding: 18px 0; border-bottom: 1px solid var(--line); }
      .archive-date { margin: 0 0 8px; color: var(--green); font-size: 0.92rem; font-weight: 800; }
      .archive-title { margin: 0 0 8px; color: var(--ink); font-size: 1.25rem; line-height: 1.2; font-weight: 850; }
      .archive-links { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 12px; }
      .pill { display: inline-flex; align-items: center; min-height: 34px; padding: 6px 11px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,0.74); color: #3f4a57; font-size: 0.88rem; font-weight: 750; text-decoration: none; }
      .note { margin: 26px 0 0; padding: 15px 16px; border: 1px solid #cfe0ed; border-radius: 14px; background: var(--soft-blue); color: #263442; }
      @media (min-width: 720px) { body { font-size: 18px; } .page { padding: 34px 32px 64px; } }
"""


@dataclass(frozen=True)
class ArchiveEntry:
    date: str
    title: str
    summary: str
    html: str
    pdf: str


def month_day_year(dt: datetime) -> str:
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def slug_from_date(dt: datetime) -> str:
    return f"daily_ai_blockchain_briefing_{dt.strftime('%Y-%m-%d')}"


def normalize_slug(text: str) -> str:
    text = re.sub(r"^\s*\d+\.\s*", "", text)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:80] or "story"


def require_key(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        print(f"Missing {name}; skipping.")
    return value


def openai_response_json(prompt: str, schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    api_key = require_key("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(0)

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    body = {
        "model": model,
        "tools": [
            {
                "type": "web_search",
                "filters": {"allowed_domains": ALLOWED_NEWS_DOMAINS},
            }
        ],
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a careful news editor for a professional AI, crypto and tech-power briefing. "
                    "Use only real, recent sources. Prefer Reuters, Financial Times, Bloomberg, CNBC, The Verge, "
                    "WSJ, TechCrunch, CoinDesk, Cointelegraph, official company blogs and regulator websites. "
                    "Do not invent references. Return only valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from exc

    text = payload.get("output_text")
    if not text:
        text = extract_output_text(payload)
    if not text:
        raise RuntimeError(f"OpenAI response did not contain output_text: {payload}")
    return json.loads(text)


def extract_output_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "".join(chunks)


def daily_schema() -> dict[str, Any]:
    reference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["publication", "article_title", "date", "url", "source_quality", "source_type", "supporting"],
        "properties": {
            "publication": {"type": "string"},
            "article_title": {"type": "string"},
            "date": {"type": "string"},
            "url": {"type": "string"},
            "source_quality": {"type": "string", "enum": ["High", "Medium-High"]},
            "source_type": {"type": "string"},
            "supporting": {"type": "string"},
        },
    }
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title",
            "reference",
            "story",
            "why",
            "watch",
        ],
        "properties": {
            "title": {"type": "string"},
            "reference": reference,
            "story": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
            "why": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
            "watch": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
        },
    }
    vocabulary = {
        "type": "array",
        "minItems": 12,
        "maxItems": 20,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["term", "meaning_cn"],
            "properties": {"term": {"type": "string"}, "meaning_cn": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["date_label", "headline", "overview", "archive_summary", "items", "vocabulary", "takeaway"],
        "properties": {
            "date_label": {"type": "string"},
            "headline": {"type": "string"},
            "overview": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
            "archive_summary": {"type": "string"},
            "items": {"type": "array", "minItems": 3, "maxItems": 5, "items": item},
            "vocabulary": vocabulary,
            "takeaway": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
        },
    }


def breaking_schema() -> dict[str, Any]:
    alert = {
        "type": "object",
        "additionalProperties": False,
        "required": ["headline", "why_it_matters", "category", "importance_score", "publication", "url", "published_at"],
        "properties": {
            "headline": {"type": "string"},
            "why_it_matters": {"type": "string"},
            "category": {"type": "string", "enum": ["AI", "Crypto", "Tech Power", "Policy", "Markets"]},
            "importance_score": {"type": "integer", "minimum": 1, "maximum": 10},
            "publication": {"type": "string"},
            "url": {"type": "string"},
            "published_at": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["alerts"],
        "properties": {"alerts": {"type": "array", "minItems": 0, "maxItems": 3, "items": alert}},
    }


def build_daily_prompt(date_label: str) -> str:
    return f"""
Create the {date_label} daily AI, Crypto & Tech Power newsletter.

Select 3 to 5 important, real news items from the last 24 to 36 hours. Quality is more important than quantity.
Focus on:
- AI: OpenAI, Anthropic, Google DeepMind, Microsoft, Meta, NVIDIA, xAI, Apple, Amazon.
- Crypto: Bitcoin, Ethereum, stablecoins, ETF, DeFi, tokenisation, crypto regulation, institutional adoption.
- Tech Power: Musk ecosystem, Tesla, SpaceX, Starlink, xAI, AI data centers, chips, energy, national-security technology.

Write in simple, natural business English. The goal is to help a reader understand the news, stay interested, and remember useful professional language. Avoid academic phrasing and repetitive sections.
Chinese is allowed only in vocabulary meanings.
Each item must include:
1. Reference
2. The story
3. Why it matters
4. What to watch

At the end, include Professional terms:
- Choose 12 to 20 reusable professional terms from business, policy, AI, crypto, finance and technology.
- Do not output generic keywords, company names, tickers, simple nouns, or one-off labels.
- If a term is an acronym or abbreviation, include the full English form beside it, for example: ETF (exchange-traded fund), SEC (Securities and Exchange Commission), GPU (graphics processing unit), LLM (large language model), CPI (Consumer Price Index).
- Keep the Chinese meaning concise in meaning_cn.

Avoid pure gossip, minor product tweaks, and weak price-only stories unless they affect policy, capital flows, infrastructure or market structure.
Use real URLs and dates. Do not use general background knowledge as a reference.
"""


def generate_daily() -> Path | None:
    date_arg = os.environ.get("NEWSLETTER_DATE")
    dt = datetime.fromisoformat(date_arg).replace(tzinfo=timezone.utc) if date_arg else datetime.now(timezone.utc)
    date_label = month_day_year(dt)
    slug = slug_from_date(dt)
    data = openai_response_json(build_daily_prompt(date_label), "daily_briefing", daily_schema())
    data["date_label"] = date_label
    dry_run = truthy(os.environ.get("DRY_RUN"))
    if dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    html_path = Path(f"{slug}.html")
    pdf_path = Path("pdf") / f"{slug}.pdf"
    html_path.write_text(render_issue_html(slug, data), encoding="utf-8")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    render_pdf(pdf_path, data)
    Path("index.html").write_text(render_issue_html(slug, data), encoding="utf-8")
    write_archive(ArchiveEntry(data["date_label"], data["headline"], data["archive_summary"], html_path.name, str(pdf_path)))
    print(f"Generated {html_path} and {pdf_path}.")
    return html_path


def render_issue_html(slug: str, issue: dict[str, Any]) -> str:
    toc = []
    articles = []
    for index, item in enumerate(issue["items"], start=1):
        story_title = re.sub(r"^\s*\d+\.\s*", "", item["title"]).strip()
        numbered = f"{index}. {story_title}"
        item_slug = normalize_slug(story_title)
        toc.append(f'          <li><a href="#{escape(item_slug)}">{escape(numbered)}</a></li>')
        articles.append(render_article(item_slug, numbered, item))

    overview = "\n".join(f"        <p>{escape(p)}</p>" for p in issue["overview"])
    takeaway = "\n".join(f"        <p>{escape(p)}</p>" for p in issue["takeaway"])
    vocabulary = "\n".join(
        f'          <li><span class="term">{escape(v["term"])}</span> - {escape(v["meaning_cn"])}</li>'
        for v in issue["vocabulary"]
    )
    pdf_href = f"pdf/{slug}.pdf"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="archive-summary" content="{escape(issue['archive_summary'], quote=True)}" />
    <title>{escape(SITE_TITLE)} - {escape(issue['date_label'])}</title>
    <style>
{HTML_STYLE}
    </style>
  </head>
  <body>
    <main class="page">
      <nav class="site-nav" aria-label="Site navigation">
        <a href="./">{escape(SITE_NAV_TITLE)}</a>
        <div class="site-nav-links">
          <a href="./">Latest</a>
          <a href="archive.html">Archive</a>
          <a href="{escape(pdf_href)}">PDF</a>
        </div>
      </nav>

      <header class="masthead">
        <p class="kicker">Daily Briefing · {escape(issue['date_label'])}</p>
        <h1>{escape(SITE_TITLE)}</h1>
        <p class="headline">{escape(issue['headline'])}</p>
        <div class="meta-row">
          <a class="pill" href="archive.html">Archive</a>
          <a class="pill" href="{escape(pdf_href)}">PDF</a>
        </div>
      </header>

      <section class="overview" aria-label="Executive overview">
{overview}
      </section>

      <nav aria-label="Briefing table of contents">
        <ol class="toc">
{chr(10).join(toc)}
        </ol>
      </nav>

{chr(10).join(articles)}

      <section class="terms">
        <h2>Professional terms</h2>
        <p class="term-note">Important business, policy, AI and crypto terms. Acronyms include the full English form.</p>
        <ul class="vocab">
{vocabulary}
        </ul>
      </section>

      <section class="takeaway">
        <h2>Today's Big Takeaway</h2>
{takeaway}
      </section>

      <p class="footer">{escape(SITE_FOOTER)} · <a href="archive.html">Archive</a> · <a href="{escape(pdf_href)}">PDF</a></p>
    </main>
  </body>
</html>
"""


def render_article(item_slug: str, numbered_title: str, item: dict[str, Any]) -> str:
    ref = item["reference"]
    story = "\n".join(f"        <p>{escape(p)}</p>" for p in item["story"])
    why = "\n".join(f"        <p>{escape(p)}</p>" for p in item["why"])
    watch = "\n".join(f"          <li>{escape(p)}</li>" for p in item["watch"])
    supporting = ""
    if ref.get("supporting"):
        supporting = f'\n          <div><span class="label">Supporting:</span> {escape(ref["supporting"])}</div>'
    return f"""      <article id="{escape(item_slug)}">
        <h2>{escape(numbered_title)}</h2>
        <section class="reference">
          <div><span class="label">Publication:</span> {escape(ref["publication"])}</div>
          <div><span class="label">Article title:</span> <em>{escape(ref["article_title"])}</em></div>
          <div><span class="label">Date:</span> {escape(ref["date"])}</div>
          <div><span class="label">Source quality:</span> {escape(ref["source_quality"])}</div>
          <div><span class="label">Source type:</span> {escape(ref["source_type"])}</div>
          <div><span class="label">Source:</span> <a href="{escape(ref["url"], quote=True)}">{escape(ref["url"])}</a></div>{supporting}
        </section>

        <h3>The story</h3>
{story}

        <h3>Why it matters</h3>
{why}

        <h3>What to watch</h3>
        <ul class="watch-list">
{watch}
        </ul>
      </article>
"""


def render_pdf(path: Path, issue: dict[str, Any]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import portrait
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import BaseDocTemplate, Frame, HRFlowable, PageTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("reportlab is required to generate PDF files.") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=22, textColor=colors.HexColor("#164a7c"), alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name="DateLine", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#667085"), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="Headline", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#17202a"), alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="ItemTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13.2, leading=16, textColor=colors.HexColor("#164a7c"), spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=colors.HexColor("#24765d"), spaceBefore=7, spaceAfter=3))
    styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.8, leading=12.4, textColor=colors.HexColor("#17202a"), spaceAfter=4))
    styles.add(ParagraphStyle(name="Ref", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.6, leading=10.5, textColor=colors.HexColor("#17202a"), spaceAfter=1))
    styles.add(ParagraphStyle(name="Vocab", parent=styles["BodyText"], fontName="STSong-Light", fontSize=8.4, leading=11.4, textColor=colors.HexColor("#17202a"), spaceAfter=1.1))
    styles.add(ParagraphStyle(name="Bullet", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.6, leading=11.8, leftIndent=10, firstLineIndent=-7, textColor=colors.HexColor("#17202a"), spaceAfter=3))

    page_size = portrait((106 * mm, 188 * mm))
    width, height = page_size
    margin = 10 * mm
    frame_width = width - 2 * margin

    def pdf_escape(text: str) -> str:
        return escape(text).replace("\n", "<br/>")

    def table_box(flowable, background, border=colors.HexColor("#cfe0ed")):
        table = Table([[flowable]], colWidths=[frame_width], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("BOX", (0, 0), (-1, -1), 0.35, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(margin, height - 7 * mm, SITE_NAV_TITLE)
        canvas.drawRightString(width - margin, height - 7 * mm, issue["date_label"])
        canvas.setStrokeColor(colors.HexColor("#ded8cc"))
        canvas.setLineWidth(0.3)
        canvas.line(margin, height - 9 * mm, width - margin, height - 9 * mm)
        canvas.drawCentredString(width / 2, 5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=page_size, leftMargin=margin, rightMargin=margin, topMargin=13 * mm, bottomMargin=9 * mm)
    frame = Frame(margin, 9 * mm, frame_width, height - 22 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="normal")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=header_footer)])
    story = [
        Spacer(1, 4),
        Paragraph(SITE_TITLE, styles["TitleBlue"]),
        Paragraph(issue["date_label"], styles["DateLine"]),
        Paragraph(pdf_escape(issue["headline"]), styles["Headline"]),
        table_box(Paragraph(pdf_escape("\n\n".join(issue["overview"])), styles["Body"]), colors.HexColor("#eaf3fb")),
        Spacer(1, 8),
    ]
    for index, item in enumerate(issue["items"], start=1):
        title = f"{index}. {re.sub(r'^\\s*\\d+\\.\\s*', '', item['title']).strip()}"
        story.append(Paragraph(pdf_escape(title), styles["ItemTitle"]))
        ref = item["reference"]
        ref_text = (
            f"<b>Publication:</b> {pdf_escape(ref['publication'])}<br/>"
            f"<b>Title:</b> <i>{pdf_escape(ref['article_title'])}</i><br/>"
            f"<b>Date:</b> {pdf_escape(ref['date'])}<br/>"
            f"<b>Source quality:</b> {pdf_escape(ref['source_quality'])}<br/>"
            f"<b>Source type:</b> {pdf_escape(ref['source_type'])}<br/>"
            f"<b>Source:</b> {pdf_escape(ref['url'])}"
        )
        if ref.get("supporting"):
            ref_text += f"<br/><b>Supporting:</b> {pdf_escape(ref['supporting'])}"
        story.append(table_box(Paragraph(ref_text, styles["Ref"]), colors.HexColor("#f5f7fa"), colors.HexColor("#ded8cc")))
        for section, key in [
            ("The story", "story"),
            ("Why it matters", "why"),
        ]:
            story.append(Paragraph(section, styles["Section"]))
            story.extend(Paragraph(pdf_escape(p), styles["Body"]) for p in item[key])
        story.append(Paragraph("What to watch", styles["Section"]))
        for bullet in item["watch"]:
            story.append(Paragraph(pdf_escape(f"• {bullet}"), styles["Bullet"]))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#ded8cc"), thickness=0.4, spaceBefore=6, spaceAfter=4))
    story.append(Paragraph("Professional terms", styles["ItemTitle"]))
    for vocab in issue["vocabulary"]:
        story.append(Paragraph(pdf_escape(f"{vocab['term']} - {vocab['meaning_cn']}"), styles["Vocab"]))
    story.append(Paragraph("Today's Big Takeaway", styles["ItemTitle"]))
    story.append(table_box(Paragraph(pdf_escape("\n\n".join(issue["takeaway"])), styles["Body"]), colors.HexColor("#edf7f2"), colors.HexColor("#c8e2d6")))
    doc.build(story)


def parse_existing_archive() -> list[ArchiveEntry]:
    path = Path("archive.html")
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[ArchiveEntry] = []
    for block in re.findall(r'<li class="archive-item">(.*?)</li>', text, flags=re.S):
        date = search_text(r'<p class="archive-date">(.*?)</p>', block)
        title = search_text(r'<h2 class="archive-title">(.*?)</h2>', block)
        paragraphs = re.findall(r"<p>(.*?)</p>", block, flags=re.S)
        summary = clean_html(paragraphs[0]) if paragraphs else ""
        html = search_text(r'href="([^"]+\.html)"', block)
        pdf = search_text(r'href="([^"]+\.pdf)"', block)
        if date and title and html and pdf:
            entries.append(ArchiveEntry(date, title, summary, html, pdf))
    return entries


def search_text(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    return clean_html(match.group(1)) if match else ""


def clean_html(text: str) -> str:
    text = re.sub(r"<.*?>", "", text)
    return unescape(" ".join(text.split()))


def write_archive(new_entry: ArchiveEntry) -> None:
    entries = [new_entry]
    seen = {new_entry.html}
    for entry in parse_existing_archive():
        if entry.html not in seen:
            entries.append(entry)
            seen.add(entry.html)
    items = []
    for entry in entries:
        items.append(f"""        <li class="archive-item">
          <p class="archive-date">{escape(entry.date)}</p>
          <h2 class="archive-title">{escape(entry.title)}</h2>
          <p>{escape(entry.summary)}</p>
          <div class="archive-links">
            <a class="pill" href="{escape(entry.html)}">Read HTML</a>
            <a class="pill" href="{escape(entry.pdf)}">Open PDF</a>
          </div>
        </li>""")
    Path("archive.html").write_text(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Archive - {escape(SITE_TITLE)}</title>
    <style>
{ARCHIVE_STYLE}
    </style>
  </head>
  <body>
    <main class="page">
      <nav class="site-nav" aria-label="Site navigation">
        <a href="./">{escape(SITE_NAV_TITLE)}</a>
        <div class="site-nav-links">
          <a href="./">Latest</a>
          <a href="archive.html">Archive</a>
        </div>
      </nav>

      <header>
        <p class="kicker">Archive</p>
        <h1>Past Briefings</h1>
        <p class="intro">A simple reading archive for the daily AI, crypto, tech power, business and policy briefing. The latest issue always lives on the home page.</p>
      </header>

      <ol class="archive-list">
{chr(10).join(items)}
      </ol>

      <section class="note">
        <p>Future daily briefings will appear here by date. The design stays intentionally simple: latest issue first, archive second, PDF for storage.</p>
      </section>
    </main>
  </body>
</html>
""", encoding="utf-8")


def breaking_prompt() -> str:
    return """
Find breaking news from the last 90 minutes in AI, crypto and tech-power.
Return up to 3 alerts only if they are genuinely important enough to interrupt subscribers.

Important examples:
- Bitcoin or Ethereum breaks a major price level because of ETF flows, macro shock, regulation or liquidation cascade.
- OpenAI, Anthropic, Google, Meta, Microsoft, NVIDIA, xAI or Apple has a major launch, funding, outage, lawsuit, safety or policy event.
- SEC, CFTC, Fed, White House, EU, UK CMA or another major regulator announces a material crypto or AI decision.
- Tesla, SpaceX, Starlink, xAI, chips, energy or AI data centers have a major market, policy or infrastructure event.

Ignore minor rumors, weak price-only moves, personality drama, and duplicate coverage.
Each alert headline should start with a natural news hook, but do not use all caps except JUST IN if appropriate.
"""


def generate_breaking() -> bool:
    if not truthy(os.environ.get("ENABLE_BREAKING_NEWS")):
        print("ENABLE_BREAKING_NEWS is not true; skipping.")
        return False
    data = openai_response_json(breaking_prompt(), "breaking_alerts", breaking_schema())
    threshold = int(os.environ.get("BREAKING_THRESHOLD", "8"))
    alerts = [a for a in data.get("alerts", []) if int(a.get("importance_score", 0)) >= threshold]
    state = load_breaking_state()
    sent_keys = {entry["key"] for entry in state}
    new_alerts = [alert for alert in alerts if alert_key(alert) not in sent_keys]
    dry_run = truthy(os.environ.get("DRY_RUN"))
    if dry_run:
        print(json.dumps({"alerts": new_alerts}, ensure_ascii=False, indent=2))
        return False
    token = require_key("TELEGRAM_BOT_TOKEN")
    chat_id = require_key("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    sent_any = False
    for alert in new_alerts[:2]:
        send_telegram(token, chat_id, build_breaking_message(alert))
        state.append({"key": alert_key(alert), "sent_at": datetime.now(timezone.utc).isoformat(), "headline": alert["headline"], "url": alert["url"]})
        sent_any = True
        print(f"Sent breaking alert: {alert['headline']}")
    if sent_any:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        BREAKING_STATE.write_text(json.dumps(state[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print("No new breaking alerts above threshold.")
    return sent_any


def alert_key(alert: dict[str, Any]) -> str:
    raw = (alert.get("url") or alert.get("headline") or "").lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def load_breaking_state() -> list[dict[str, Any]]:
    if not BREAKING_STATE.exists():
        return []
    return json.loads(BREAKING_STATE.read_text(encoding="utf-8"))


def build_breaking_message(alert: dict[str, Any]) -> str:
    headline = alert["headline"]
    if not headline.upper().startswith("JUST IN"):
        headline = f"JUST IN: {headline}"
    return "\n".join([
        f"<b>{escape(headline)}</b>",
        "",
        f"<b>Why it matters:</b> {escape(alert['why_it_matters'])}",
        "",
        f"<b>Category:</b> {escape(alert['category'])}",
        f"<b>Source:</b> <a href=\"{escape(alert['url'], quote=True)}\">{escape(alert['publication'])}</a>",
    ])


def send_telegram(token: str, chat_id: str, message: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": False},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")


def truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["daily", "breaking"])
    args = parser.parse_args()
    if args.mode == "daily":
        generate_daily()
    else:
        generate_breaking()
    return 0


if __name__ == "__main__":
    sys.exit(main())

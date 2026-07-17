#!/usr/bin/env python3
"""Generate and send a daily B2 pregnancy-English story to Telegram."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5"
STATE_PATH = Path("data/pregnancy_english_state.json")
VANCOUVER = ZoneInfo("America/Vancouver")
TELEGRAM_LIMIT = 3900


COURSE_STAGES = [
    "hospital appointments, registration, referrals, and the healthcare team",
    "fertility consultation, medical history, physical exams, and diagnostic tests",
    "sperm, semen, eggs, embryos, IVF, donors, and gestational surrogacy",
    "early pregnancy, first appointments, bloodwork, urine tests, and early scans",
    "first-trimester screening, NIPT, the NT scan, and common symptoms",
    "second-trimester care, the anatomy scan, fetal movement, and routine monitoring",
    "third-trimester care, glucose screening, GBS testing, and birth planning",
    "full-term appointments, fetal position, cervical checks, NSTs, and BPPs",
    "signs of labour, contractions, waters breaking, triage, and hospital admission",
    "the stages of labour, fetal monitoring, pain relief, and communication with staff",
    "vaginal birth, assisted birth, induction, and caesarean birth",
    "postpartum recovery, feeding, newborn tests, discharge, and a joyful homecoming",
]


def truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"last_day": 0, "learned_terms": [], "story_summary": ""}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def lesson_schema() -> dict[str, Any]:
    vocabulary = {
        "type": "object",
        "additionalProperties": False,
        "required": ["term", "meaning_cn", "usage"],
        "properties": {
            "term": {"type": "string"},
            "meaning_cn": {"type": "string"},
            "usage": {"type": "string"},
        },
    }
    sentence = {
        "type": "object",
        "additionalProperties": False,
        "required": ["english", "chinese"],
        "properties": {
            "english": {"type": "string"},
            "chinese": {"type": "string"},
        },
    }
    difference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["region", "term", "note_cn"],
        "properties": {
            "region": {"type": "string"},
            "term": {"type": "string"},
            "note_cn": {"type": "string"},
        },
    }
    quiz = {
        "type": "object",
        "additionalProperties": False,
        "required": ["question", "answer"],
        "properties": {
            "question": {"type": "string"},
            "answer": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title",
            "scene",
            "story_paragraphs",
            "story_summary",
            "vocabulary",
            "sentences",
            "regional_differences",
            "quiz",
        ],
        "properties": {
            "title": {"type": "string"},
            "scene": {"type": "string"},
            "story_paragraphs": {
                "type": "array",
                "minItems": 5,
                "maxItems": 9,
                "items": {"type": "string"},
            },
            "story_summary": {"type": "string"},
            "vocabulary": {
                "type": "array",
                "minItems": 10,
                "maxItems": 12,
                "items": vocabulary,
            },
            "sentences": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": sentence,
            },
            "regional_differences": {
                "type": "array",
                "minItems": 0,
                "maxItems": 3,
                "items": difference,
            },
            "quiz": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": quiz,
            },
        },
    }


def build_prompt(day: int, state: dict[str, Any]) -> str:
    week = min((day - 1) // 7, len(COURSE_STAGES) - 1)
    weekday = (day - 1) % 7
    lesson_type = "new story lesson"
    if weekday == 5:
        lesson_type = "weekly review story; reuse key terms naturally but still add useful new collocations"
    elif weekday == 6:
        lesson_type = "light weekly recap and bridge to next week's stage"

    learned = state.get("learned_terms", [])
    learned_text = ", ".join(learned[-300:]) or "None yet"
    previous_summary = state.get("story_summary") or "The story has not started."
    return f"""
Write Day {day} of a 12-week B2 pregnancy-English reading course.

Today's course stage: {COURSE_STAGES[week]}.
Lesson type: {lesson_type}.
Previous story summary: {previous_summary}
Terms recently taught: {learned_text}

Create one warm, hopeful, medically realistic continuing story about intended parents Alex and Jordan and their gestational carrier Maya. Begin with healthcare access and fertility care, then move chronologically through assisted reproduction, pregnancy, labour, birth, postpartum care, and a joyful homecoming. Treat every person with dignity. Do not create an emergency merely for drama and do not give personal medical advice.

The English narrative must be CEFR B2: natural, readable, and about 450-650 words in total. Necessary medical terms may exceed B2, but explain them with clear B2 English or concise Chinese. Include realistic dialogue with staff and family. Use Canadian/North American wording by default. Do not repeat US, UK, and Australian terms when they are identical. Add a regional difference only when people genuinely use a different everyday term, such as prenatal/antenatal, egg retrieval/egg collection, labor ward/labour ward spelling, or gas and air/nitrous oxide.

Naturally include 10-12 high-frequency words, collocations, or medical terms. Prefer terms the family will hear or need to say. Do not present a recently taught term as new unless today is a review lesson. Keep sperm distinct from semen, egg from ovum/oocyte, and gestational carrier from a traditional/genetic surrogate. Include real common examination and test names at the appropriate stage.

Return only JSON matching the schema. Do not use Markdown inside JSON strings. Put the English story in story_paragraphs. Chinese is allowed in meanings, translations, and regional notes.
"""


def extract_output_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "".join(chunks)


def generate_lesson(day: int, state: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    body = {
        "model": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        "input": [
            {
                "role": "system",
                "content": (
                    "You are an expert B2 English teacher and a careful reproductive, maternity, "
                    "and newborn-health terminology editor. Return accurate, respectful, valid JSON."
                ),
            },
            {"role": "user", "content": build_prompt(day, state)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pregnancy_english_lesson",
                "strict": True,
                "schema": lesson_schema(),
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from exc
    output = extract_output_text(payload)
    if not output:
        raise RuntimeError("OpenAI response did not contain output text")
    return json.loads(output)


def lesson_blocks(day: int, lesson: dict[str, Any]) -> list[str]:
    today = datetime.now(VANCOUVER).strftime("%B %d, %Y")
    blocks = [
        f"<b>🌱 B2 Pregnancy English · Day {day}</b>\n{escape(today)}",
        f"<b>{escape(lesson['title'])}</b>\n<i>{escape(lesson['scene'])}</i>",
    ]
    blocks.extend(escape(paragraph) for paragraph in lesson["story_paragraphs"])
    blocks.append("<b>今日词汇</b>")
    for item in lesson["vocabulary"]:
        blocks.append(
            f"• <b>{escape(item['term'])}</b> — {escape(item['meaning_cn'])}\n  {escape(item['usage'])}"
        )

    blocks.append("<b>实用句子</b>")
    for item in lesson["sentences"]:
        blocks.append(f"• {escape(item['english'])}\n  {escape(item['chinese'])}")

    if lesson["regional_differences"]:
        blocks.append("<b>地区差异（仅列真正不同的说法）</b>")
        for item in lesson["regional_differences"]:
            blocks.append(
                f"• {escape(item['region'])}: <b>{escape(item['term'])}</b> — {escape(item['note_cn'])}"
            )

    quiz_lines = ["<b>30秒复习</b>"]
    answer_lines = ["<b>答案</b>"]
    for index, item in enumerate(lesson["quiz"], start=1):
        quiz_lines.append(f"{index}. {escape(item['question'])}")
        answer_lines.append(f"{index}. {escape(item['answer'])}")
    blocks.append("\n".join(quiz_lines))
    blocks.append("\n".join(answer_lines))
    return blocks


def pack_messages(blocks: list[str]) -> list[str]:
    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= TELEGRAM_LIMIT:
            current = candidate
            continue
        if current:
            messages.append(current)
        if len(block) > TELEGRAM_LIMIT:
            raise ValueError("A lesson block exceeds Telegram's safe message length")
        current = block
    if current:
        messages.append(current)
    return messages


def send_telegram(token: str, chat_id: str, message: str) -> None:
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
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")


def save_state(day: int, state: dict[str, Any], lesson: dict[str, Any]) -> None:
    learned = list(state.get("learned_terms", []))
    seen = {term.casefold() for term in learned}
    for item in lesson["vocabulary"]:
        term = item["term"].strip()
        if term.casefold() not in seen:
            learned.append(term)
            seen.add(term.casefold())
    new_state = {
        "last_day": day,
        "learned_terms": learned,
        "story_summary": lesson["story_summary"],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    dry_run = truthy(os.environ.get("DRY_RUN"))
    existing_lesson = os.environ.get("LESSON_JSON")
    if existing_lesson:
        lesson_path = Path(existing_lesson)
        payload = json.loads(lesson_path.read_text(encoding="utf-8"))
        day = int(payload["day"])
        lesson = payload["lesson"]
        messages = pack_messages(lesson_blocks(day, lesson))
        if dry_run:
            for index, message in enumerate(messages, start=1):
                print(f"--- Telegram message {index}/{len(messages)} ---")
                print(message)
            return 0
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        for message in messages:
            send_telegram(token, chat_id, message)
        print(f"Sent saved B2 pregnancy English Day {day} in {len(messages)} Telegram messages.")
        return 0

    state = load_state()
    day = int(state.get("last_day", 0)) + 1
    lesson = generate_lesson(day, state)
    messages = pack_messages(lesson_blocks(day, lesson))

    if dry_run:
        for index, message in enumerate(messages, start=1):
            print(f"--- Telegram message {index}/{len(messages)} ---")
            print(message)
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    for message in messages:
        send_telegram(token, chat_id, message)
    save_state(day, state, lesson)
    print(f"Sent B2 pregnancy English Day {day} in {len(messages)} Telegram messages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

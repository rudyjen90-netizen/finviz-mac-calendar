#!/usr/bin/env python3
"""Build an Apple-compatible ICS feed from Finviz's US economic calendar.

This is an unofficial, small personal-use converter. It uses only Python's
standard library and interprets Finviz event times as America/New_York time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


FINVIZ_API = "https://finviz.com/api/calendar/economic"
FINVIZ_PAGE = "https://finviz.com/calendar/economic"
NEW_YORK = ZoneInfo("America/New_York")
UTC = timezone.utc


TRANSLATIONS = {
    "Non Farm Payrolls": "非农就业人数",
    "Unemployment Rate": "失业率",
    "Initial Jobless Claims": "首次申请失业救济人数",
    "Continuing Jobless Claims": "持续申请失业救济人数",
    "Average Hourly Earnings MoM": "平均时薪（月率）",
    "Average Hourly Earnings YoY": "平均时薪（年率）",
    "CPI MoM": "消费者物价指数（月率）",
    "CPI YoY": "消费者物价指数（年率）",
    "Core CPI MoM": "核心消费者物价指数（月率）",
    "Core CPI YoY": "核心消费者物价指数（年率）",
    "PCE Price Index MoM": "PCE物价指数（月率）",
    "PCE Price Index YoY": "PCE物价指数（年率）",
    "Core PCE Price Index MoM": "核心PCE物价指数（月率）",
    "Core PCE Price Index YoY": "核心PCE物价指数（年率）",
    "Fed Interest Rate Decision": "美联储利率决议",
    "FOMC Economic Projections": "美联储经济预测",
    "FOMC Press Conference": "美联储新闻发布会",
    "FOMC Minutes": "美联储会议纪要",
    "GDP Growth Rate QoQ": "GDP增长率（季率）",
    "Retail Sales MoM": "零售销售（月率）",
    "Retail Sales YoY": "零售销售（年率）",
    "ISM Manufacturing PMI": "ISM制造业PMI",
    "ISM Services PMI": "ISM服务业PMI",
    "JOLTs Job Openings": "JOLTS职位空缺",
    "Michigan Consumer Sentiment": "密歇根消费者信心",
    "Conference Board Consumer Confidence": "谘商会消费者信心",
    "Durable Goods Orders MoM": "耐用品订单（月率）",
    "PPI MoM": "生产者物价指数（月率）",
    "PPI YoY": "生产者物价指数（年率）",
    "Core PPI MoM": "核心生产者物价指数（月率）",
    "Core PPI YoY": "核心生产者物价指数（年率）",
}


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def request_json(url: str, attempts: int = 3) -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Referer": FINVIZ_PAGE,
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                payload = json.load(response)
                if not isinstance(payload, list):
                    raise RuntimeError("Finviz returned an unexpected data format")
                return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not download Finviz calendar: {last_error}")


def fetch_entries(weeks_back: int, weeks_ahead: int) -> list[dict]:
    base = monday_of(datetime.now(NEW_YORK).date())
    by_id: dict[str, dict] = {}

    for week_offset in range(-weeks_back, weeks_ahead + 1):
        start = base + timedelta(weeks=week_offset)
        end = start + timedelta(days=4)
        url = FINVIZ_API + "?" + urlencode(
            {"dateFrom": start.isoformat(), "dateTo": end.isoformat()}
        )
        for item in request_json(url):
            calendar_id = item.get("calendarId")
            if calendar_id is not None:
                by_id[str(calendar_id)] = item
        time.sleep(0.7)  # Keep request volume gentle.

    return list(by_id.values())


def parse_event_datetime(value: str) -> datetime:
    naive = datetime.fromisoformat(value)
    if naive.tzinfo is not None:
        return naive.astimezone(UTC)
    return naive.replace(tzinfo=NEW_YORK).astimezone(UTC)


def escape_ics(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ics_line(line: str, limit: int = 70) -> list[str]:
    """Fold a content line conservatively by UTF-8 byte count."""
    if len(line.encode("utf-8")) <= limit:
        return [line]

    output: list[str] = []
    remaining = line
    first = True
    while remaining:
        prefix = "" if first else " "
        room = limit - len(prefix.encode("utf-8"))
        used = 0
        cut = 0
        for index, char in enumerate(remaining):
            size = len(char.encode("utf-8"))
            if used + size > room:
                break
            used += size
            cut = index + 1
        if cut == 0:
            cut = 1
        output.append(prefix + remaining[:cut])
        remaining = remaining[cut:]
        first = False
    return output


def localized_name(original: str) -> str:
    if original in TRANSLATIONS:
        return f"{TRANSLATIONS[original]}｜{original}"
    if original.startswith("Fed ") and original.endswith(" Speech"):
        speaker = original.removeprefix("Fed ").removesuffix(" Speech")
        return f"美联储 {speaker} 讲话｜{original}"
    return original


def detail_line(label: str, value: object) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}: {value}"


def event_lines(item: dict, reminder_minutes: int) -> list[str]:
    start = parse_event_datetime(str(item["date"]))
    end = start + timedelta(minutes=30)
    importance = int(item.get("importance") or 0)
    level = "高影响" if importance >= 3 else "中影响"
    icon = "🔴" if importance >= 3 else "🟠"
    original_name = str(item.get("event") or item.get("category") or "Economic event")
    summary = f"{icon} {level}｜{localized_name(original_name)}"

    details = [
        f"Finviz 美国经济日历｜{level}",
        detail_line("公布值", item.get("actual")),
        detail_line("预测值", item.get("forecast")),
        detail_line("前值", item.get("previous")),
        detail_line("期间", item.get("reference")),
        detail_line("类别", item.get("category")),
        "时间会由 Apple 日历自动转换为设备所在时区。",
        f"来源: {FINVIZ_PAGE}",
    ]
    description = "\n".join(part for part in details if part)
    uid = f"finviz-{item['calendarId']}@economic-calendar"
    stamp = start.strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{escape_ics(uid)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{stamp}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(description)}",
        f"URL:{FINVIZ_PAGE}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
    ]
    if reminder_minutes > 0:
        lines.extend(
            [
                "BEGIN:VALARM",
                f"TRIGGER:-PT{reminder_minutes}M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{escape_ics(summary)}",
                "END:VALARM",
            ]
        )
    lines.append("END:VEVENT")
    return lines


def build_calendar(entries: list[dict], min_importance: int, reminder_minutes: int) -> bytes:
    selected: list[tuple[datetime, dict]] = []
    for item in entries:
        try:
            importance = int(item.get("importance") or 0)
            if importance < min_importance or item.get("allDay"):
                continue
            start = parse_event_datetime(str(item["date"]))
            selected.append((start, item))
        except (KeyError, TypeError, ValueError):
            continue

    selected.sort(key=lambda pair: (pair[0], str(pair[1].get("calendarId", ""))))
    if not selected:
        raise RuntimeError("No matching calendar events were found; existing feed was kept")

    logical_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal Finviz Economic Calendar//ZH-CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:美股经济日历（Finviz）",
        "X-WR-CALDESC:Finviz 美国中高影响经济事件，自动更新并提前提醒",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for _, item in selected:
        logical_lines.extend(event_lines(item, reminder_minutes))
    logical_lines.append("END:VCALENDAR")

    physical_lines: list[str] = []
    for line in logical_lines:
        physical_lines.extend(fold_ics_line(line))
    return ("\r\n".join(physical_lines) + "\r\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/finviz-economic.ics")
    parser.add_argument("--weeks-back", type=int, default=1)
    parser.add_argument("--weeks-ahead", type=int, default=4)
    parser.add_argument("--min-importance", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--reminder-minutes", type=int, default=30)
    args = parser.parse_args()

    try:
        entries = fetch_entries(args.weeks_back, args.weeks_ahead)
        calendar = build_calendar(entries, args.min_importance, args.reminder_minutes)
        atomic_write(Path(args.output), calendar)
        print(f"Updated {args.output} from {len(entries)} source entries")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

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


SPEAKER_TRANSLATIONS = {
    "Powell": "鲍威尔",
    "Goolsbee": "古尔斯比",
    "Waller": "沃勒",
    "Williams": "威廉姆斯",
    "Bowman": "鲍曼",
    "Jefferson": "杰斐逊",
    "Collins": "柯林斯",
    "Daly": "戴利",
    "Kashkari": "卡什卡利",
    "Bostic": "博斯蒂克",
    "Barkin": "巴尔金",
    "Logan": "洛根",
    "Musalem": "穆萨莱姆",
    "Cook": "库克",
    "Barr": "巴尔",
    "Hammack": "哈马克",
    "Schmid": "施密德",
}


CATEGORY_TRANSLATIONS = {
    "Interest Rate": "利率与美联储",
    "Inflation Rate": "通胀",
    "Labour": "就业",
    "Labor": "就业",
    "Employment": "就业",
    "GDP": "经济增长",
    "Business": "企业与制造业",
    "Consumer": "消费",
    "Housing": "房地产",
    "Government": "政府与财政",
    "Money": "货币与信贷",
    "Trade": "贸易",
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
        return TRANSLATIONS[original]
    if original.startswith("Fed ") and original.endswith(" Speech"):
        speaker = original.removeprefix("Fed ").removesuffix(" Speech")
        speaker_zh = SPEAKER_TRANSLATIONS.get(speaker, speaker)
        return f"美联储{speaker_zh}讲话"
    return original


def category_name(category: object) -> str | None:
    if category is None or category == "":
        return None
    raw = str(category)
    return CATEGORY_TRANSLATIONS.get(raw, raw)


def detail_line(label: str, value: object) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}：{value}"


def beginner_notes(original_name: str, category: object) -> tuple[str, str, str, str, str]:
    name = original_name.lower()
    cat = str(category or "").lower()

    if original_name.startswith("Fed ") and original_name.endswith(" Speech"):
        speaker = original_name.removeprefix("Fed ").removesuffix(" Speech")
        speaker_zh = SPEAKER_TRANSLATIONS.get(speaker, speaker)
        return (
            f"这是美联储官员{speaker_zh}的公开讲话。",
            "市场会听他如何评价通胀、经济和未来利率，讲话可能改变市场对降息或加息路径的预期。",
            "如果讲话强调通胀继续回落、经济放缓，或更接近降息，通常对美股偏利好。",
            "如果强调通胀仍顽固、利率需要更久维持高位，甚至可能再次加息，通常对美股偏利空。",
            "讲话前后几分钟波动可能突然放大。不要只看标题，要看原话是否超出市场原本预期。",
        )

    if "interest rate" in name or "fomc" in name or "interest rate" in cat:
        return (
            "这是和美联储利率政策直接相关的重要事件。",
            "利率预期会直接影响股票估值、美元和美债收益率，因此往往能迅速带动大盘波动。",
            "如果结果或措辞比市场预期更偏向降息，通常对美股偏利好。",
            "如果比预期更偏向维持高利率或加息，通常对美股偏利空。",
            "最重要的是和市场预期比较，而不是只看“降息”或“加息”几个字。",
        )

    if any(key in name for key in ("cpi", "pce", "ppi", "inflation")) or "inflation" in cat:
        return (
            "这是观察美国物价涨得快不快的通胀数据。",
            "通胀会影响美联储何时降息或是否需要继续维持高利率，因此常会影响美股、美元和美债。",
            "如果通胀低于市场预测，通常有利于降息预期，对美股偏利好。",
            "如果通胀高于市场预测，通常会压低降息预期，对美股偏利空。",
            "重点比较“公布值”和“预测值”。差距越大，市场反应通常越明显。",
        )

    if any(key in name for key in ("payroll", "unemployment", "jobless", "jolts", "employment", "earnings")) or any(key in cat for key in ("labour", "labor", "employment")):
        return (
            "这是观察美国就业市场强弱的数据。",
            "就业会影响经济增长和美联储利率判断，是市场判断降息节奏的重要依据。",
            "就业适度降温、但没有明显衰退迹象时，通常更有利于降息预期。",
            "就业过热可能让降息更慢；如果突然恶化得太快，也可能引发经济衰退担忧。",
            "不要简单理解成“越低越好”或“越高越好”，要结合失业率、工资和市场预期一起看。",
        )

    if "gdp" in name or "gdp" in cat:
        return (
            "这是观察美国经济增长速度的数据。",
            "经济增长强弱会影响企业盈利预期，同时也会影响美联储对利率的判断。",
            "增长稳健且通胀不过热，通常对股市更友好。",
            "增长明显低于预期可能引发衰退担忧；增长过热也可能让降息推迟。",
            "GDP不能单独判断涨跌方向，要结合通胀和利率预期一起看。",
        )

    if any(key in name for key in ("retail sales", "consumer confidence", "consumer sentiment")) or "consumer" in cat:
        return (
            "这是观察美国消费者花钱意愿和消费强弱的数据。",
            "美国消费占经济比重很大，消费变化会影响企业盈利和经济增长预期。",
            "数据稳健但不过热，通常更有利于股市。",
            "数据明显过弱可能引发经济放缓担忧；过强也可能推高利率维持高位的预期。",
            "重点看公布值和预测值的差距，以及市场当时更担心通胀还是衰退。",
        )

    if "pmi" in name or "ism" in name or "business" in cat:
        return (
            "这是观察企业景气、订单和经营活动强弱的数据。",
            "它能较早反映经济是在扩张还是放缓，因此会影响增长和企业盈利预期。",
            "数据温和改善通常偏利好，尤其是同时没有明显通胀压力时。",
            "数据明显恶化可能引发经济放缓担忧；过热也可能让降息预期降温。",
            "关注是否高于或低于市场预测，并结合价格分项和就业分项理解。",
        )

    return (
        "这是美国经济日历中的重要数据或政策事件。",
        "它可能改变市场对经济、通胀或利率的判断，从而影响美股、美元和美债。",
        "如果结果比市场预期更有利于经济稳定和利率下降，通常对美股偏利好。",
        "如果结果增加通胀、高利率或经济衰退担忧，通常对美股偏利空。",
        "最关键的是和“市场预测”比较，不能只看数据本身高或低。",
    )


def event_lines(item: dict, reminder_minutes: int) -> list[str]:
    start = parse_event_datetime(str(item["date"]))
    end = start + timedelta(minutes=30)
    importance = int(item.get("importance") or 0)
    if importance >= 3:
        level, icon = "高影响", "🔴"
    elif importance == 2:
        level, icon = "中影响", "🟠"
    else:
        level, icon = "低影响", "⚪"

    original_name = str(item.get("event") or item.get("category") or "经济事件")
    summary = f"{icon} {level}｜{localized_name(original_name)}"
    simple, why, bullish, bearish, caution = beginner_notes(
        original_name, item.get("category")
    )

    details = [
        f"Finviz 美国经济日历｜{level}",
        f"新手解释：{simple}",
        f"为什么重要：{why}",
        f"偏利好时：{bullish}",
        f"偏利空时：{bearish}",
        f"新手注意：{caution}",
        detail_line("公布值", item.get("actual")),
        detail_line("预测值", item.get("forecast")),
        detail_line("前值", item.get("previous")),
        detail_line("期间", item.get("reference")),
        detail_line("类别", category_name(item.get("category"))),
        "时间：会自动按设备所在时区显示。",
        "来源：Finviz",
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

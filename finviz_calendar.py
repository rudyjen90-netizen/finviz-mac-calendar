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
from datetime import date, datetime, timedelta, timezone
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
    "MBA 30-Year Mortgage Rate": "美国30年期按揭贷款利率",
    "ADP Employment Change Weekly": "ADP每周就业变化",
    "ADP Employment Change": "ADP就业变化",
    "API Crude Oil Stock Change": "API原油库存变化",
    "EIA Crude Oil Stocks Change": "EIA原油库存变化",
    "EIA Gasoline Stocks Change": "EIA汽油库存变化",
    "Non Farm Payrolls": "非农就业人数",
    "Unemployment Rate": "失业率",
    "Participation Rate": "劳动参与率",
    "Initial Jobless Claims": "首次申请失业救济人数",
    "Continuing Jobless Claims": "持续申请失业救济人数",
    "Average Hourly Earnings MoM": "平均时薪（月率）",
    "Average Hourly Earnings YoY": "平均时薪（年率）",
    "CPI MoM": "消费者物价指数（月率）",
    "CPI YoY": "消费者物价指数（年率）",
    "Core CPI MoM": "核心消费者物价指数（月率）",
    "Core CPI YoY": "核心消费者物价指数（年率）",
    "CPI": "消费者物价指数",
    "CPI s.a": "经季调消费者物价指数",
    "Inflation Rate MoM": "通胀率（月率）",
    "Inflation Rate YoY": "通胀率（年率）",
    "Core Inflation Rate MoM": "核心通胀率（月率）",
    "Core Inflation Rate YoY": "核心通胀率（年率）",
    "PCE Price Index MoM": "PCE物价指数（月率）",
    "PCE Price Index YoY": "PCE物价指数（年率）",
    "Core PCE Price Index MoM": "核心PCE物价指数（月率）",
    "Core PCE Price Index YoY": "核心PCE物价指数（年率）",
    "Fed Interest Rate Decision": "美联储利率决议",
    "FOMC Economic Projections": "美联储经济预测",
    "FOMC Press Conference": "美联储新闻发布会",
    "Fed Press Conference": "美联储新闻发布会",
    "FOMC Minutes": "美联储会议纪要",
    "GDP Growth Rate QoQ": "GDP增长率（季率）",
    "GDP Growth Rate QoQ Final": "GDP增长率（季率终值）",
    "GDP Price Index QoQ Final": "GDP价格指数（季率终值）",
    "Retail Sales MoM": "零售销售（月率）",
    "Retail Sales YoY": "零售销售（年率）",
    "Retail Sales Ex Autos MoM": "剔除汽车的零售销售（月率）",
    "Retail Sales Control Group MoM": "零售销售控制组（月率）",
    "ISM Manufacturing PMI": "ISM制造业PMI",
    "ISM Services PMI": "ISM服务业PMI",
    "ISM Manufacturing Employment": "ISM制造业就业指数",
    "JOLTs Job Openings": "JOLTS职位空缺",
    "Michigan Consumer Sentiment": "密歇根消费者信心",
    "Michigan Consumer Sentiment Prel": "密歇根消费者信心（初值）",
    "Michigan Consumer Sentiment Final": "密歇根消费者信心（终值）",
    "Conference Board Consumer Confidence": "谘商会消费者信心",
    "CB Consumer Confidence": "谘商会消费者信心",
    "Durable Goods Orders MoM": "耐用品订单（月率）",
    "Durable Goods Orders Ex Transp MoM": "剔除运输的耐用品订单（月率）",
    "PPI MoM": "生产者物价指数（月率）",
    "PPI YoY": "生产者物价指数（年率）",
    "Core PPI MoM": "核心生产者物价指数（月率）",
    "Core PPI YoY": "核心生产者物价指数（年率）",
    "Existing Home Sales": "成屋销售",
    "Existing Home Sales MoM": "成屋销售（月率）",
    "New Home Sales": "新屋销售",
    "New Home Sales MoM": "新屋销售（月率）",
    "Pending Home Sales MoM": "待售房屋销售（月率）",
    "Pending Home Sales YoY": "待售房屋销售（年率）",
    "Housing Starts": "新屋开工",
    "Housing Starts MoM": "新屋开工（月率）",
    "Building Permits Prel": "营建许可（初值）",
    "Building Permits MoM Prel": "营建许可（月率初值）",
    "NAHB Housing Market Index": "NAHB房地产市场指数",
    "S&P/Case-Shiller Home Price YoY": "标普／凯斯席勒房价指数（年率）",
    "Industrial Production MoM": "工业产出（月率）",
    "Factory Orders MoM": "工厂订单（月率）",
    "Business Inventories MoM": "商业库存（月率）",
    "Wholesale Inventories MoM Adv": "批发库存（月率初值）",
    "Retail Inventories Ex Autos MoM Adv": "剔除汽车的零售库存（月率初值）",
    "NY Empire State Manufacturing Index": "纽约州制造业指数",
    "Philadelphia Fed Manufacturing Index": "费城联储制造业指数",
    "Dallas Fed Manufacturing Index": "达拉斯联储制造业指数",
    "Chicago Fed National Activity Index": "芝加哥联储全国活动指数",
    "Chicago PMI": "芝加哥采购经理指数",
    "Import Prices MoM": "进口价格（月率）",
    "Export Prices MoM": "出口价格（月率）",
    "Personal Spending MoM": "个人支出（月率）",
    "Personal Income MoM": "个人收入（月率）",
    "Monthly Budget Statement": "联邦预算月报",
    "Current Account": "经常账户",
    "Goods Trade Balance Adv": "商品贸易余额（初值）",
    "Balance of Trade": "贸易余额",
    "Imports": "进口额",
    "Exports": "出口额",
    "Net Long-term TIC Flows": "长期资本净流入",
    "President Trump and President Xi Summit": "特朗普总统与习近平主席峰会",
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
    "Paulson": "保尔森",
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
    "Oil": "能源与原油",
    "Government Budget": "政府与财政",
    "Home Ownership": "房地产",
    "Housing Starts": "房地产",
    "Consumer Confidence": "消费与信心",
    "Manufacturing": "制造业",
}


# The course starts on the Monday this training version was introduced.  Each
# weekday has one lesson; an eight-week pass covers the full curriculum and
# then repeats so the ideas can be reinforced in live market conditions.
COURSE_START = date(2026, 9, 21)
COURSE_STAGES = (
    (
        "看懂经济日历",
        (
            (
                "市场交易的是预期差",
                "数据本身好或坏并不是第一重点。真正推动价格的，往往是公布结果比市场原先预测高了多少或低了多少。",
            ),
            (
                "分清公布值、预测值和前值",
                "公布值是这次答案，预测值是市场考前猜测，前值是上次成绩。先比较公布值与预测值，再参考前值判断趋势。",
            ),
            (
                "修正值会改写故事",
                "不少数据会修改上个月的数字。即使本月符合预测，前值若被大幅上修或下修，市场仍可能重新定价。",
            ),
            (
                "重要数据也不等于必涨必跌",
                "“高影响”只表示可能引起较大波动，不代表方向。方向取决于预期差、当时的市场主线和仓位拥挤程度。",
            ),
            (
                "把单项数据放进组合",
                "一次数据只是拼图之一。把通胀、就业、增长和美联储放在一起看，结论才比单看一个数字可靠。",
            ),
        ),
    ),
    (
        "理解美联储",
        (
            (
                "美联储的双重目标",
                "美联储同时追求充分就业和物价稳定。通胀过高时更重视压通胀，就业快速恶化时更重视保增长。",
            ),
            (
                "利率怎样传到股价",
                "政策利率会影响融资成本和股票估值。利率预期下降通常有利于成长股估值，但若原因是严重衰退，股市未必上涨。",
            ),
            (
                "什么是鹰派与鸽派",
                "鹰派更担心通胀、倾向高利率；鸽派更担心增长和就业、倾向低利率。市场最在意语气是否比预期更鹰或更鸽。",
            ),
            (
                "点阵图不是承诺",
                "点阵图展示官员对未来利率的个人判断，会随数据变化。它是路径线索，不是美联储保证一定执行的时间表。",
            ),
            (
                "听讲话要寻找变化",
                "不要只给官员贴鹰派或鸽派标签。比较他这次与上次措辞的变化，才更容易找到真正影响市场的新信息。",
            ),
        ),
    ),
    (
        "读懂美债与利率",
        (
            (
                "2年期收益率看政策预期",
                "2年期美债收益率对未来几次美联储行动更敏感。数据公布后它快速上升，常表示市场认为利率会更高或降息会更晚。",
            ),
            (
                "10年期收益率看长期定价",
                "10年期美债收益率混合了增长、通胀和期限补偿。它上升时，长期现金流的现值下降，成长股估值容易承压。",
            ),
            (
                "收益率与债券价格反向",
                "市场收益率上升时，旧债券固定利息变得不够吸引，价格会下降；收益率下降时，旧债券价格通常上升。",
            ),
            (
                "实际利率为何影响成长股",
                "实际利率大致等于名义收益率减去通胀预期。实际利率上升，远期利润折现得更厉害，QQQ往往更敏感。",
            ),
            (
                "收益率曲线在说什么",
                "短端高于长端叫倒挂，常反映紧政策与未来放缓预期；曲线重新变陡还要分清是降息预期还是长期通胀上升造成。",
            ),
        ),
    ),
    (
        "理解通胀",
        (
            (
                "CPI观察消费者物价",
                "消费者物价指数反映居民购买的一篮子商品和服务价格。月率更能看近期速度，年率更容易受一年前基数影响。",
            ),
            (
                "核心通胀为何重要",
                "核心指标剔除波动较大的食品和能源，更容易观察持续性压力，但普通人的实际生活成本仍会受到食品和能源影响。",
            ),
            (
                "PCE是美联储偏爱的口径",
                "PCE物价指数覆盖更广，也会调整消费替代行为。美联储设定通胀目标时更重视核心PCE。",
            ),
            (
                "PPI观察上游价格",
                "生产者物价指数反映企业投入和出厂价格。它可能领先部分消费通胀，但企业能否把成本转嫁给消费者同样关键。",
            ),
            (
                "黏性服务通胀",
                "住房、工资相关服务价格通常下降较慢。商品降价不等于通胀问题结束，服务分项往往决定最后一公里是否顺利。",
            ),
        ),
    ),
    (
        "理解就业",
        (
            (
                "非农为何最受关注",
                "非农就业显示企业新增岗位，是判断经济热度的重要数据。要与失业率、工资和前值修正一起看，不能只盯一个人数。",
            ),
            (
                "失业率也要看参与率",
                "失业率上升可能是工作变少，也可能是更多人重新进入劳动力市场。结合劳动参与率才能更准确理解原因。",
            ),
            (
                "工资连接就业与通胀",
                "工资增长支持消费，但过快也可能令服务通胀更顽固。市场会用平均时薪判断就业是否仍给通胀施压。",
            ),
            (
                "职位空缺与ADP只是线索",
                "JOLTS和ADP能提供就业方向线索，但统计口径不同，不能当成非农的精确答案。分歧本身也可能造成波动。",
            ),
            (
                "初请失业金看拐点",
                "单周初请容易受节假日和天气扰动。连续数周趋势比某一周的跳动更能说明裁员是否真正升温。",
            ),
        ),
    ),
    (
        "理解经济增长",
        (
            (
                "GDP是经济总成绩单",
                "GDP衡量一段时间的总产出，但公布较慢且会修正。市场更关注增长组成和未来趋势，而不只是一个总数。",
            ),
            (
                "PMI和ISM较早反映方向",
                "采购经理调查通常领先硬数据。高于50常表示活动扩张，低于50常表示收缩，但变化速度同样重要。",
            ),
            (
                "零售销售观察消费",
                "消费是美国经济的重要支柱。控制组更接近GDP中的消费口径；同时要分清名义增长是否只是价格上涨造成。",
            ),
            (
                "房地产是利率敏感温度计",
                "按揭利率会影响购房能力、开工和销售。房地产转弱可能拖累增长，但供应短缺也会让房价与销量出现分化。",
            ),
            (
                "领先指标与滞后指标",
                "订单、信心和金融条件往往较早变化，就业和GDP确认较慢。交易要找领先线索，判断则要等多项数据互相印证。",
            ),
        ),
    ),
    (
        "理解市场反应",
        (
            (
                "为什么好数据也会跌",
                "若市场最担心高利率，好数据可能推迟降息，股市反而下跌；若市场最担心衰退，同一份好数据又可能利好。",
            ),
            (
                "第一反应不一定是真方向",
                "算法会在几秒内交易标题数字，随后资金会分析分项和修正值。先观察美债、美元与指数能否同向确认。",
            ),
            (
                "用跨市场信号做确认",
                "同时看2年期与10年期美债收益率、美元指数、QQQ和SPY。多个市场讲同一个故事时，结论通常更可信。",
            ),
            (
                "行业敏感度不同",
                "利率上升时长久期成长股更敏感；油价变化直接影响能源股；消费和小盘股对经济增长与融资条件更敏感。",
            ),
            (
                "利好兑现与仓位拥挤",
                "价格可能在事件前已提前上涨。结果即使不错，只要没有超过高预期，获利盘也可能卖出，这就是利好兑现。",
            ),
        ),
    ),
    (
        "建立交易纪律",
        (
            (
                "催化剂不是买入理由的全部",
                "事件只能提供波动时间窗。入场前还要有方向依据、失效条件和退出计划，不能因为“会波动”就下注。",
            ),
            (
                "先算风险收益比",
                "先确定错了在哪里止损，再估算合理目标。潜在收益明显大于可承受亏损时，机会才值得继续研究。",
            ),
            (
                "仓位决定能否活下来",
                "再高胜率也会遇到错误。单笔亏损必须小到不会破坏账户和下一次机会，杠杆更要按最坏情景计算。",
            ),
            (
                "不追第一根剧烈波动",
                "重大数据后的第一根走势常伴随滑点和假突破。等价格、美债和成交量完成确认，通常比猜第一秒更稳健。",
            ),
            (
                "复盘过程而不是只看盈亏",
                "记录预测差、跨市场反应、自己的判断和执行。赚钱但违反纪律也要纠正，亏钱但过程正确则保留方法。",
            ),
        ),
    ),
)


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
    return CATEGORY_TRANSLATIONS.get(raw, localized_name(raw))


def detail_line(label: str, value: object) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}：{value}"


def event_kind(original_name: str, category: object) -> str:
    name = original_name.lower()
    cat = str(category or "").lower()

    if (
        original_name.startswith("Fed ")
        or "fomc" in name
        or "interest rate" in name
        or "interest rate" in cat
    ):
        return "fed"
    if any(key in name for key in ("cpi", "pce", "ppi", "inflation", "price")) or "inflation" in cat:
        return "inflation"
    if any(key in name for key in ("payroll", "unemployment", "jobless", "jolts", "employment", "earnings", "participation")) or any(key in cat for key in ("labour", "labor", "employment")):
        return "employment"
    if any(key in name for key in ("crude oil", "gasoline", "petroleum")) or "oil" in cat:
        return "oil"
    if any(key in name for key in ("home", "housing", "mortgage", "building permit", "case-shiller", "nahb")) or "housing" in cat:
        return "housing"
    if any(key in name for key in ("retail sales", "consumer confidence", "consumer sentiment", "personal spending", "personal income")) or "consumer" in cat:
        return "consumer"
    if any(key in name for key in ("gdp", "pmi", "ism", "activity index", "industrial production", "factory orders", "manufacturing", "inventories")) or any(key in cat for key in ("gdp", "business", "manufacturing", "activity index")):
        return "growth"
    if any(key in name for key in ("trade", "imports", "exports", "current account", "tic flows")) or "trade" in cat:
        return "trade"
    if any(key in name for key in ("budget", "summit", "president")) or "government" in cat:
        return "policy"
    return "general"


def training_lesson(start: datetime) -> tuple[str, str]:
    local_day = start.astimezone(NEW_YORK).date()
    week_offset = (local_day - COURSE_START).days // 7
    stage_index = week_offset % len(COURSE_STAGES)
    lesson_index = min(local_day.weekday(), 4)
    stage_name, lessons = COURSE_STAGES[stage_index]
    title, body = lessons[lesson_index]
    heading = (
        f"第{stage_index + 1}阶段·第{lesson_index + 1}课｜"
        f"{stage_name}：{title}"
    )
    return heading, body


def market_watch(original_name: str, category: object) -> tuple[str, str]:
    kind = event_kind(original_name, category)
    if kind == "fed":
        return (
            "2年期与10年期美债收益率、美元指数、QQQ/SPY、利率期货中的降息概率",
            "政策信息 → 利率路径预期 → 美债收益率与美元 → 股票估值 → QQQ/SPY",
        )
    if kind == "inflation":
        return (
            "2年期美债收益率、美元指数、QQQ/SPY、核心与非核心分项",
            "通胀预期差 → 降息预期 → 美债收益率与美元 → 成长股估值 → QQQ/SPY",
        )
    if kind == "employment":
        return (
            "2年期美债收益率、美元指数、QQQ/SPY、失业率与工资是否互相确认",
            "就业强弱 → 软着陆或衰退判断 → 利率与盈利预期 → 指数和行业表现",
        )
    if kind == "oil":
        return (
            "美国原油价格、能源板块、库存变化原因、美元指数",
            "库存与需求变化 → 油价 → 能源股与通胀预期 → 美债收益率和大盘",
        )
    if kind == "housing":
        return (
            "10年期美债收益率、按揭利率、住宅建筑与房地产相关股票、SPY",
            "利率与购房能力 → 销售和开工 → 经济增长预期 → 周期板块与大盘",
        )
    if kind == "consumer":
        return (
            "SPY、QQQ、可选消费板块、10年期美债收益率",
            "消费强弱 → 企业收入与经济增长 → 通胀和利率预期 → 指数与消费板块",
        )
    if kind == "growth":
        return (
            "SPY、QQQ、小盘股、2年期与10年期美债收益率、周期板块",
            "增长预期差 → 盈利与衰退判断 → 利率预期 → 指数与周期板块",
        )
    if kind == "trade":
        return (
            "美元指数、美债收益率、SPY、出口与制造业相关板块",
            "贸易与资金流 → 美元和增长预期 → 企业盈利 → 指数与相关行业",
        )
    if kind == "policy":
        return (
            "美元指数、美债收益率、SPY/QQQ、受政策直接影响的行业",
            "政策信息 → 关税、财政或监管预期 → 通胀与盈利 → 指数和行业",
        )
    return (
        "2年期与10年期美债收益率、美元指数、QQQ/SPY",
        "数据预期差 → 利率与经济判断 → 美债和美元 → 股票估值与盈利预期",
    )


def beginner_notes(original_name: str, category: object) -> tuple[str, str, str, str, str]:
    name = original_name.lower()
    cat = str(category or "").lower()
    kind = event_kind(original_name, category)

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

    if kind == "fed":
        return (
            "这是和美联储利率政策直接相关的重要事件。",
            "利率预期会直接影响股票估值、美元和美债收益率，因此往往能迅速带动大盘波动。",
            "如果结果或措辞比市场预期更偏向降息，通常对美股偏利好。",
            "如果比预期更偏向维持高利率或加息，通常对美股偏利空。",
            "最重要的是和市场预期比较，而不是只看“降息”或“加息”几个字。",
        )

    if kind == "inflation":
        return (
            "这是观察美国物价涨得快不快的通胀数据。",
            "通胀会影响美联储何时降息或是否需要继续维持高利率，因此常会影响美股、美元和美债。",
            "如果通胀低于市场预测，通常有利于降息预期，对美股偏利好。",
            "如果通胀高于市场预测，通常会压低降息预期，对美股偏利空。",
            "重点比较“公布值”和“预测值”。差距越大，市场反应通常越明显。",
        )

    if kind == "employment":
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

    if kind == "consumer":
        return (
            "这是观察美国消费者花钱意愿和消费强弱的数据。",
            "美国消费占经济比重很大，消费变化会影响企业盈利和经济增长预期。",
            "数据稳健但不过热，通常更有利于股市。",
            "数据明显过弱可能引发经济放缓担忧；过强也可能推高利率维持高位的预期。",
            "重点看公布值和预测值的差距，以及市场当时更担心通胀还是衰退。",
        )

    if kind == "growth":
        return (
            "这是观察企业景气、订单和经营活动强弱的数据。",
            "它能较早反映经济是在扩张还是放缓，因此会影响增长和企业盈利预期。",
            "数据温和改善通常偏利好，尤其是同时没有明显通胀压力时。",
            "数据明显恶化可能引发经济放缓担忧；过热也可能让降息预期降温。",
            "关注是否高于或低于市场预测，并结合价格分项和就业分项理解。",
        )

    if kind == "housing":
        return (
            "这是观察美国房地产销售、开工、许可或融资成本的数据。",
            "房地产对利率很敏感，又会影响建筑、消费和银行，因此是观察经济周期的重要窗口。",
            "数据稳健且按揭利率没有明显上升，通常更有利于软着陆和周期板块。",
            "数据显著走弱可能增加经济放缓担忧；过热和房价压力也可能使利率更久维持高位。",
            "房屋销量、价格和开工可能方向不同，要先判断变化来自需求、利率还是供应。",
        )

    if kind == "oil":
        return (
            "这是观察美国原油或成品油库存变化的数据。",
            "库存能反映短期供需，油价又会影响能源股、运输成本和通胀预期。",
            "库存降幅大于预测通常支持油价和能源股，但仍要确认炼厂开工、进口和需求。",
            "库存增幅大于预测通常压制油价和能源股，但供应中断可能改变结论。",
            "API是行业统计，EIA是官方统计；两者有时差异很大，不要把前者当成最终答案。",
        )

    if kind == "trade":
        return (
            "这是观察美国进出口、国际收支或跨境资金流的数据。",
            "它会影响美元、制造业、经济增长和海外资金对美国资产的需求。",
            "出口和长期资金流强于预期，通常有利于增长或资产需求，但要结合美元变化理解。",
            "贸易恶化或资金流明显转弱可能带来增长和融资担忧。",
            "贸易差额不能简单用正负判断好坏，要区分进口需求、能源价格和汇率造成的变化。",
        )

    if kind == "policy":
        return (
            "这是可能影响财政、关税、监管或国际关系的政策事件。",
            "政策变化可能直接改写企业成本、通胀、供应链和行业盈利预期。",
            "如果不确定性下降、关税或监管压力减轻，通常对相关行业偏利好。",
            "如果冲突、关税或财政压力上升，通常会增加通胀和盈利风险。",
            "政策事件最容易出现标题误读，要等正式文件或双方确认，不凭单一消息追涨杀跌。",
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
    watch, chain = market_watch(original_name, item.get("category"))
    lesson_heading, lesson_body = training_lesson(start)

    sections = [
        [
            f"Finviz 美国经济日历｜{level}",
            f"新手解释：{simple}",
            f"为什么重要：{why}",
        ],
        [
            "【数据对比】",
            detail_line("公布值", item.get("actual")),
            detail_line("预测值", item.get("forecast")),
            detail_line("前值", item.get("previous")),
            detail_line("期间", item.get("reference")),
            "判断顺序：先比较公布值与预测值，再看前值有没有被修正；没有预测值时不要硬判方向。",
        ],
        [
            "【情景判断】",
            f"偏利好时：{bullish}",
            f"偏利空时：{bearish}",
            f"新手注意：{caution}",
        ],
        [
            "【市场观察】",
            f"传导链：{chain}",
            f"重点观察：{watch}",
        ],
        [
            "【今日学习卡】",
            lesson_heading,
            lesson_body,
        ],
        [
            "【公布后复盘】",
            "1. 公布值与预测值差多少？前值是否修正？",
            "2. 美债收益率和美元的第一反应是什么？",
            "3. QQQ与SPY是否确认这个方向？为什么？",
        ],
        [
            detail_line("类别", category_name(item.get("category"))),
            "来源：Finviz",
        ],
    ]
    description = "\n\n".join(
        "\n".join(part for part in section if part) for section in sections
    )
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
        "X-WR-CALDESC:美股经济事件提醒与8阶段新手训练课，自动更新并提前提醒",
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

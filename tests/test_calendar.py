import unittest
from datetime import datetime, timezone

import finviz_calendar as calendar


SAMPLE_EVENT = {
    "calendarId": 12345,
    "date": "2026-09-21T08:30:00",
    "importance": 3,
    "event": "CPI MoM",
    "actual": "0.2%",
    "forecast": "0.3%",
    "previous": "0.4%",
    "reference": "Aug",
    "category": "Inflation Rate",
    "allDay": False,
}


def unfolded(content: bytes) -> str:
    return content.decode("utf-8").replace("\r\n ", "")


class CalendarTests(unittest.TestCase):
    def test_learning_event_has_requested_sections(self) -> None:
        output = unfolded(calendar.build_calendar([SAMPLE_EVENT], 2, 30))

        self.assertIn("🔴 高影响｜消费者物价指数（月率）", output)
        self.assertIn("【数据对比】", output)
        self.assertIn("【市场观察】", output)
        self.assertIn("【今日学习卡】", output)
        self.assertIn("【公布后复盘】", output)
        self.assertIn("第1阶段·第1课｜看懂经济日历：市场交易的是预期差", output)
        self.assertNotIn("时间：会自动按设备所在时区显示", output)

    def test_course_moves_to_next_stage_each_week(self) -> None:
        first_title, _ = calendar.training_lesson(
            datetime(2026, 9, 21, 14, tzinfo=timezone.utc)
        )
        second_title, _ = calendar.training_lesson(
            datetime(2026, 9, 28, 14, tzinfo=timezone.utc)
        )

        self.assertIn("第1阶段", first_title)
        self.assertIn("看懂经济日历", first_title)
        self.assertIn("第2阶段", second_title)
        self.assertIn("理解美联储", second_title)

    def test_same_day_uses_same_lesson(self) -> None:
        morning = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
        afternoon = datetime(2026, 10, 6, 19, tzinfo=timezone.utc)
        self.assertEqual(
            calendar.training_lesson(morning),
            calendar.training_lesson(afternoon),
        )

    def test_current_english_events_have_chinese_titles(self) -> None:
        self.assertEqual(calendar.localized_name("Existing Home Sales"), "成屋销售")
        self.assertEqual(
            calendar.localized_name("Chicago Fed National Activity Index"),
            "芝加哥联储全国活动指数",
        )
        self.assertEqual(
            calendar.localized_name("Fed Paulson Speech"),
            "美联储保尔森讲话",
        )

    def test_ics_lines_are_folded_safely(self) -> None:
        output = calendar.build_calendar([SAMPLE_EVENT], 2, 30)
        for line in output.split(b"\r\n"):
            self.assertLessEqual(len(line), 70)

    def test_low_importance_events_are_filtered(self) -> None:
        low = dict(SAMPLE_EVENT, calendarId=999, importance=1)
        with self.assertRaisesRegex(RuntimeError, "No matching calendar events"):
            calendar.build_calendar([low], 2, 30)


if __name__ == "__main__":
    unittest.main()

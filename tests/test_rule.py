import io
import unittest
from contextlib import redirect_stdout
from datetime import date

from rrulelite.cli import main
from rrulelite.rule import RuleError, expand, parse_date, parse_rule


class ParseTest(unittest.TestCase):
    def test_rule_pairs(self):
        self.assertEqual(
            parse_rule("FREQ=DAILY;COUNT=2"),
            {"FREQ": "DAILY", "COUNT": "2"},
        )

    def test_keys_are_uppercased(self):
        self.assertEqual(list(parse_rule("freq=daily")), ["FREQ"])

    def test_parse_date(self):
        self.assertEqual(parse_date("2026-01-05"), date(2026, 1, 5))


class DailyTest(unittest.TestCase):
    def test_three_days(self):
        self.assertEqual(
            expand("FREQ=DAILY;COUNT=3", date(2026, 1, 1)),
            [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
        )

    def test_interval(self):
        self.assertEqual(
            expand("FREQ=DAILY;INTERVAL=2;COUNT=3", date(2026, 1, 1)),
            [date(2026, 1, 1), date(2026, 1, 3), date(2026, 1, 5)],
        )

    def test_byday_filter(self):
        self.assertEqual(
            expand("FREQ=DAILY;BYDAY=MO;COUNT=2", date(2026, 1, 1)),
            [date(2026, 1, 5), date(2026, 1, 12)],
        )

    def test_until_truncates(self):
        self.assertEqual(
            expand("FREQ=DAILY;UNTIL=2026-01-02", date(2026, 1, 1)),
            [date(2026, 1, 1), date(2026, 1, 2)],
        )


class CliTest(unittest.TestCase):
    def test_prints_iso_dates(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--rule", "FREQ=DAILY;COUNT=2", "--start", "2026-01-01"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().split(), ["2026-01-01", "2026-01-02"])

    def test_missing_arguments(self):
        self.assertEqual(main(["--rule", "FREQ=DAILY"]), 2)


if __name__ == "__main__":
    unittest.main()


class WeeklyIntervalTest(unittest.TestCase):
    def test_biweekly_monday_from_thursday(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4", date(2026, 1, 1)),
            [date(2026, 1, 5), date(2026, 1, 19), date(2026, 2, 2), date(2026, 2, 16)],
        )

    def test_interval_three(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;INTERVAL=3;BYDAY=TU;COUNT=3", date(2026, 1, 6)),
            [date(2026, 1, 6), date(2026, 1, 27), date(2026, 2, 17)],
        )

    def test_start_included_when_matching(self):
        days = expand("FREQ=WEEKLY;BYDAY=MO;COUNT=2", date(2026, 1, 5))
        self.assertEqual(days[0], date(2026, 1, 5))


class BydayOrderTest(unittest.TestCase):
    def test_sorted_and_increasing(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=WE,MO;COUNT=4", date(2026, 1, 5)),
            [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 12), date(2026, 1, 14)],
        )

    def test_duplicates_removed(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=MO,MO,WE,MO;COUNT=3", date(2026, 1, 5)),
            [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 12)],
        )

    def test_same_week_days_in_order(self):
        days = expand("FREQ=WEEKLY;BYDAY=SU,MO;COUNT=4", date(2026, 1, 5))
        self.assertEqual(days, [date(2026, 1, 5), date(2026, 1, 11), date(2026, 1, 12), date(2026, 1, 18)])


class MonthlyTest(unittest.TestCase):
    def test_skips_months_without_the_day(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;BYMONTHDAY=31;COUNT=3", date(2026, 1, 31)),
            [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)],
        )

    def test_defaults_to_start_day(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;COUNT=3", date(2026, 1, 31)),
            [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)],
        )

    def test_interval_months(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=15;COUNT=3", date(2026, 1, 15)),
            [date(2026, 1, 15), date(2026, 3, 15), date(2026, 5, 15)],
        )

    def test_until_inclusive(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;BYMONTHDAY=31;UNTIL=2026-03-31", date(2026, 1, 31)),
            [date(2026, 1, 31), date(2026, 3, 31)],
        )

    def test_count_truncated_by_until(self):
        days = expand("FREQ=DAILY;COUNT=10;UNTIL=2026-01-03", date(2026, 1, 1))
        self.assertEqual(days, [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)])


class InvalidRuleTest(unittest.TestCase):
    def assert_rule_error(self, text, needle):
        with self.assertRaises(RuleError) as ctx:
            expand(text, date(2026, 1, 1))
        self.assertIn(needle, str(ctx.exception))

    def test_unknown_freq(self):
        self.assert_rule_error("FREQ=HOURLY", "第 1 项")

    def test_unknown_key(self):
        self.assert_rule_error("FREQ=DAILY;BYHOUR=3", "第 2 项")

    def test_missing_value(self):
        self.assert_rule_error("FREQ=DAILY;INTERVAL=", "第 2 项")

    def test_missing_equals(self):
        self.assert_rule_error("FREQ=DAILY;COUNT", "第 2 项")

    def test_interval_not_a_number(self):
        self.assert_rule_error("FREQ=DAILY;INTERVAL=abc", "第 2 项")

    def test_interval_zero(self):
        self.assert_rule_error("FREQ=DAILY;INTERVAL=0", "第 2 项")

    def test_interval_negative(self):
        self.assert_rule_error("FREQ=DAILY;INTERVAL=-2", "第 2 项")

    def test_bymonthday_out_of_range(self):
        self.assert_rule_error("FREQ=MONTHLY;BYMONTHDAY=32", "第 2 项")
        self.assert_rule_error("FREQ=MONTHLY;BYMONTHDAY=0", "第 2 项")

    def test_byday_invalid_name(self):
        self.assert_rule_error("FREQ=WEEKLY;BYDAY=MO,XX", "第 2 项")

    def test_bad_until(self):
        self.assert_rule_error("FREQ=DAILY;UNTIL=2026/01/01", "第 2 项")

    def test_parse_date_raises_rule_error(self):
        with self.assertRaises(RuleError):
            parse_date("2026年1月1日")


class InvariantTest(unittest.TestCase):
    RULES = [
        "FREQ=DAILY;COUNT=30",
        "FREQ=DAILY;INTERVAL=3;BYDAY=MO,FR;COUNT=20",
        "FREQ=WEEKLY;INTERVAL=2;BYDAY=WE,MO;COUNT=20",
        "FREQ=WEEKLY;INTERVAL=3;BYDAY=SU;COUNT=10",
        "FREQ=MONTHLY;BYMONTHDAY=31;COUNT=10",
        "FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=29;COUNT=10",
        "FREQ=MONTHLY;COUNT=8;UNTIL=2027-06-30",
    ]
    STARTS = [date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 28), date(2026, 12, 30)]

    def test_strictly_increasing(self):
        for rule in self.RULES:
            for start in self.STARTS:
                days = expand(rule, start)
                self.assertEqual(days, sorted(set(days)), rule)
                for earlier, later in zip(days, days[1:]):
                    self.assertLess(earlier, later, rule)

    def test_deterministic(self):
        for rule in self.RULES:
            self.assertEqual(expand(rule, date(2026, 1, 1)), expand(rule, date(2026, 1, 1)))

    def test_matches_brute_force_reference(self):
        for rule in self.RULES:
            for start in self.STARTS:
                self.assertEqual(expand(rule, start), reference_expand(rule, start), rule)


class PerformanceTest(unittest.TestCase):
    def test_daily_large_interval_no_spinning(self):
        import time

        began = time.perf_counter()
        days = expand("FREQ=DAILY;INTERVAL=500;COUNT=5000", date(2026, 1, 1))
        elapsed = time.perf_counter() - began
        self.assertEqual(len(days), 5000)
        self.assertLess(elapsed, 0.1)

    def test_weekly_and_monthly_5000(self):
        import time

        began = time.perf_counter()
        self.assertEqual(len(expand("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE;COUNT=5000", date(2026, 1, 1))), 5000)
        self.assertEqual(len(expand("FREQ=MONTHLY;BYMONTHDAY=31;COUNT=5000", date(2026, 1, 31))), 5000)
        self.assertLess(time.perf_counter() - began, 0.1)


def reference_expand(rule_text, start):
    """参考实现：逐日扫描再过滤，只用于小跨度对照。"""
    from datetime import timedelta

    from rrulelite.rule import WEEKDAYS, parse_rule

    rule = parse_rule(rule_text)
    freq = rule.get("FREQ", "DAILY").upper()
    interval = int(rule.get("INTERVAL", "1"))
    if "COUNT" in rule:
        count = int(rule["COUNT"])
    else:
        count = 10 if "UNTIL" not in rule else 10 ** 9
    until = parse_date(rule["UNTIL"]) if "UNTIL" in rule else None
    byday = None
    if "BYDAY" in rule:
        byday = sorted(
            {part.strip().upper() for part in rule["BYDAY"].split(",") if part.strip()},
            key=WEEKDAYS.index,
        )
    bymonthday = int(rule["BYMONTHDAY"]) if "BYMONTHDAY" in rule else None

    weekly_names = byday or [WEEKDAYS[start.weekday()]]
    first = min(
        start + timedelta(days=(WEEKDAYS.index(name) - start.weekday()) % 7)
        for name in weekly_names
    )
    anchor_monday = first - timedelta(days=first.weekday())

    out = []
    day = start
    scanned = 0
    while len(out) < count and scanned < 40000:
        scanned += 1
        if until is not None and day > until:
            break
        if freq == "DAILY":
            match = (day - start).days % interval == 0 and (
                not byday or WEEKDAYS[day.weekday()] in byday
            )
        elif freq == "WEEKLY":
            monday = day - timedelta(days=day.weekday())
            match = ((monday - anchor_monday).days // 7) % interval == 0 and (
                WEEKDAYS[day.weekday()] in weekly_names
            )
        else:
            diff = (day.year * 12 + day.month) - (start.year * 12 + start.month)
            match = diff % interval == 0 and day.day == (bymonthday or start.day)
        if match:
            out.append(day)
        day += timedelta(days=1)
    return out

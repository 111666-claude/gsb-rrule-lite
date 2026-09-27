import io
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta

from rrulelite.cli import main
from rrulelite.rule import RuleError, WEEKDAYS, expand, parse_date, parse_rule


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
    def test_every_two_weeks(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4", date(2026, 1, 1)),
            [date(2026, 1, 5), date(2026, 1, 19), date(2026, 2, 2), date(2026, 2, 16)],
        )

    def test_default_weekday_is_start_weekday(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;COUNT=2", date(2026, 1, 1)),
            [date(2026, 1, 1), date(2026, 1, 8)],
        )


class MonthlyTest(unittest.TestCase):
    def test_skips_months_without_31st(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;BYMONTHDAY=31;COUNT=3", date(2026, 1, 31)),
            [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)],
        )

    def test_default_monthday_is_start_day(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;COUNT=3", date(2026, 1, 31)),
            [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)],
        )

    def test_interval_months(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=15;COUNT=3", date(2026, 1, 15)),
            [date(2026, 1, 15), date(2026, 3, 15), date(2026, 5, 15)],
        )

    def test_leap_day(self):
        self.assertEqual(
            expand("FREQ=MONTHLY;BYMONTHDAY=29;COUNT=3", date(2026, 1, 29)),
            [date(2026, 1, 29), date(2026, 3, 29), date(2026, 4, 29)],
        )


class BydayTest(unittest.TestCase):
    def test_sorted_regardless_of_written_order(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=WE,MO;COUNT=4", date(2026, 1, 5)),
            [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 12), date(2026, 1, 14)],
        )

    def test_dedup(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=MO,MO,MO;COUNT=2", date(2026, 1, 5)),
            [date(2026, 1, 5), date(2026, 1, 12)],
        )

    def test_chronological_within_first_week(self):
        # 起始日是周四，同一周内周日在周一之前
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=SU,MO;COUNT=3", date(2026, 1, 1)),
            [date(2026, 1, 4), date(2026, 1, 5), date(2026, 1, 11)],
        )


class BoundaryTest(unittest.TestCase):
    def test_start_included_when_matching(self):
        self.assertEqual(
            expand("FREQ=WEEKLY;BYDAY=TH;COUNT=2", date(2026, 1, 1)),
            [date(2026, 1, 1), date(2026, 1, 8)],
        )

    def test_until_inclusive(self):
        self.assertEqual(
            expand("FREQ=DAILY;UNTIL=2026-01-03", date(2026, 1, 1))[-1],
            date(2026, 1, 3),
        )

    def test_until_truncates_count(self):
        self.assertEqual(
            len(expand("FREQ=DAILY;COUNT=10;UNTIL=2026-01-03", date(2026, 1, 1))),
            3,
        )


class ValidationTest(unittest.TestCase):
    def assert_item_error(self, rule, index):
        with self.assertRaises(RuleError) as caught:
            expand(rule, date(2026, 1, 1))
        self.assertIn("第 %d 项" % index, str(caught.exception))

    def test_unknown_key(self):
        self.assert_item_error("FREQ=DAILY;FOO=1", 2)

    def test_missing_value(self):
        self.assert_item_error("FREQ=DAILY;COUNT", 2)
        self.assert_item_error("FREQ=DAILY;COUNT=", 2)

    def test_bad_freq(self):
        self.assert_item_error("FREQ=YEARLY", 1)

    def test_bad_interval(self):
        self.assert_item_error("FREQ=DAILY;INTERVAL=0", 2)
        self.assert_item_error("FREQ=DAILY;INTERVAL=-2", 2)
        self.assert_item_error("FREQ=DAILY;INTERVAL=abc", 2)

    def test_bymonthday_out_of_range(self):
        self.assert_item_error("FREQ=MONTHLY;BYMONTHDAY=0", 2)
        self.assert_item_error("FREQ=MONTHLY;BYMONTHDAY=32", 2)

    def test_bad_byday(self):
        self.assert_item_error("FREQ=WEEKLY;BYDAY=XX", 2)

    def test_bad_until(self):
        self.assert_item_error("FREQ=DAILY;UNTIL=2026-13-01", 2)

    def test_parse_date_raises_rule_error(self):
        with self.assertRaises(RuleError):
            parse_date("2026/01/01")


def _reference_expand(rule_text, start, days=800):
    """逐日扫描再过滤的参考实现。"""
    rule = parse_rule(rule_text)
    freq = rule.get("FREQ", "DAILY").upper()
    interval = int(rule.get("INTERVAL", "1"))
    count = int(rule.get("COUNT", "10"))
    until = parse_date(rule["UNTIL"]) if "UNTIL" in rule else None
    byday = None
    if "BYDAY" in rule:
        byday = {WEEKDAYS.index(name) for name in rule["BYDAY"].split(",")}
    bymonthday = None
    if "BYMONTHDAY" in rule:
        bymonthday = {int(part) for part in rule["BYMONTHDAY"].split(",")}
    if freq == "WEEKLY" and byday is None:
        byday = {start.weekday()}
    if freq == "MONTHLY" and bymonthday is None:
        bymonthday = {start.day}
    out = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        if until is not None and day > until:
            break
        if freq == "DAILY":
            ok = offset % interval == 0
        elif freq == "WEEKLY":
            ok = (offset // 7) % interval == 0
        else:
            ok = ((day.year - start.year) * 12 + day.month - start.month) % interval == 0
        if byday is not None and day.weekday() not in byday:
            ok = False
        if bymonthday is not None and day.day not in bymonthday:
            ok = False
        if ok:
            out.append(day)
            if len(out) >= count:
                break
    return out


class InvariantTest(unittest.TestCase):
    RULES = [
        "FREQ=DAILY;INTERVAL=3;COUNT=8",
        "FREQ=DAILY;BYDAY=MO,FR;COUNT=6",
        "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4",
        "FREQ=WEEKLY;BYDAY=WE,MO;COUNT=6",
        "FREQ=WEEKLY;INTERVAL=3;BYDAY=SU,MO,TH;COUNT=7",
        "FREQ=MONTHLY;BYMONTHDAY=31;COUNT=5",
        "FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=15;COUNT=4",
        "FREQ=MONTHLY;COUNT=4",
        "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4;UNTIL=2026-03-01",
    ]

    def test_matches_reference(self):
        for rule in self.RULES:
            for start in (date(2026, 1, 1), date(2026, 1, 5), date(2026, 1, 31)):
                self.assertEqual(
                    expand(rule, start),
                    _reference_expand(rule, start),
                    "%s from %s" % (rule, start),
                )

    def test_strictly_increasing_and_deterministic(self):
        for rule in self.RULES:
            first = expand(rule, date(2026, 1, 1))
            self.assertEqual(first, expand(rule, date(2026, 1, 1)))
            self.assertEqual(first, sorted(set(first)))
            for earlier, later in zip(first, first[1:]):
                self.assertLess(earlier, later)


class PerformanceTest(unittest.TestCase):
    def test_daily_large_interval_does_not_spin(self):
        from datetime import timedelta

        self.assertEqual(
            expand("FREQ=DAILY;INTERVAL=1000;COUNT=3", date(2026, 1, 1)),
            [date(2026, 1, 1) + timedelta(days=1000 * k) for k in range(3)],
        )

    def test_count_5000_fast(self):
        import time

        begun = time.perf_counter()
        for rule in (
            "FREQ=DAILY;INTERVAL=7;COUNT=5000",
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR;COUNT=5000",
            "FREQ=MONTHLY;BYMONTHDAY=31;COUNT=5000",
        ):
            self.assertEqual(len(expand(rule, date(2026, 1, 1))), 5000)
        self.assertLess(time.perf_counter() - begun, 0.5)

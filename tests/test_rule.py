import io
import unittest
from contextlib import redirect_stdout
from datetime import date

from rrulelite.cli import main
from rrulelite.rule import expand, parse_date, parse_rule


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

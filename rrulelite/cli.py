"""命令行入口：按规则展开日期，一行一个。"""

import argparse
import sys

from .rule import RuleError, expand, parse_date


def build_parser():
    parser = argparse.ArgumentParser(prog="rrule-lite", description="重复规则展开（RFC 5545 子集）")
    parser.add_argument("--rule", help="例如 FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4")
    parser.add_argument("--start", help="起始日期 YYYY-MM-DD")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.rule or not args.start:
        print("错误：需要 --rule 与 --start", file=sys.stderr)
        return 2
    try:
        days = expand(args.rule, parse_date(args.start))
    except (RuleError, ValueError) as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    for day in days:
        print(day.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

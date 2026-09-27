"""重复规则展开（RFC 5545 子集）。只用标准库。

口径：
- WEEKLY 以首个不早于起始日的匹配周为锚，每 INTERVAL 周取一周；
- DAILY 每隔 INTERVAL 天，大步长时不逐天空转；
- MONTHLY 按自然月推进，没有 BYMONTHDAY 那一天的月份跳过；
- BYDAY 按周一..周日排序去重，输出严格递增；
- 起始日符合规则时包含，UNTIL 含当天，COUNT 是最终条数。
"""

import calendar
from datetime import date, timedelta

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
FREQS = ("DAILY", "WEEKLY", "MONTHLY")
ALLOWED_KEYS = ("FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "COUNT", "UNTIL")
DEFAULT_COUNT = 10


class RuleError(ValueError):
    """规则不合法，message 里指出是第几项。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _parse_items(text):
    """把规则串拆成 (键值 dict, 键 -> 第几项)，校验键名与缺值。"""
    items = {}
    positions = {}
    index = 0
    for raw in text.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        index += 1
        key, sep, value = raw.partition("=")
        key = key.strip().upper()
        value = value.strip()
        if not sep or not key or not value:
            raise RuleError("第 %d 项 %r：缺键或缺值" % (index, raw))
        if key not in ALLOWED_KEYS:
            raise RuleError("第 %d 项 %r：未知键 %r" % (index, raw, key))
        items[key] = value
        positions[key] = index
    return items, positions


def parse_rule(text):
    """解析 "FREQ=WEEKLY;COUNT=5"，未知键、缺值会抛 RuleError 并指出第几项。"""
    return _parse_items(text)[0]


def parse_date(text):
    """解析 YYYY-MM-DD，格式不对抛 RuleError。"""
    try:
        year, month, day = text.strip().split("-")
        return date(int(year), int(month), int(day))
    except (AttributeError, ValueError):
        raise RuleError("日期 %r 不是合法的 YYYY-MM-DD" % (text,))


def _positive_int(rule, positions, key):
    raw = rule[key]
    try:
        value = int(raw)
    except ValueError:
        raise RuleError("第 %d 项：%s=%r 不是正整数" % (positions[key], key, raw))
    if value < 1:
        raise RuleError("第 %d 项：%s=%r 必须是 >= 1 的正整数" % (positions[key], key, raw))
    return value


def _byday(rule, positions):
    if "BYDAY" not in rule:
        return None
    names = []
    for part in rule["BYDAY"].split(","):
        name = part.strip().upper()
        if not name:
            continue
        if name not in WEEKDAYS:
            raise RuleError(
                "第 %d 项：BYDAY 含非法星期名 %r" % (positions["BYDAY"], name)
            )
        if name not in names:
            names.append(name)
    # 按周一..周日排序
    names.sort(key=WEEKDAYS.index)
    return names or None


def _validate(rule, positions):
    freq = rule.get("FREQ", "DAILY").upper()
    if freq not in FREQS:
        raise RuleError(
            "第 %d 项：FREQ=%r 不是 DAILY/WEEKLY/MONTHLY" % (positions["FREQ"], rule["FREQ"])
        )
    interval = _positive_int(rule, positions, "INTERVAL") if "INTERVAL" in rule else 1
    if "COUNT" in rule:
        count = _positive_int(rule, positions, "COUNT")
    elif "UNTIL" in rule:
        count = None  # 有 UNTIL 没 COUNT：展开到 UNTIL 为止
    else:
        count = DEFAULT_COUNT
    until = None
    if "UNTIL" in rule:
        try:
            until = parse_date(rule["UNTIL"])
        except RuleError as error:
            raise RuleError("第 %d 项：%s" % (positions["UNTIL"], error.message))
    bymonthday = None
    if "BYMONTHDAY" in rule:
        bymonthday = _positive_int(rule, positions, "BYMONTHDAY")
        if bymonthday > 31:
            raise RuleError(
                "第 %d 项：BYMONTHDAY=%r 不在 1..31"
                % (positions["BYMONTHDAY"], rule["BYMONTHDAY"])
            )
    return freq, interval, count, until, _byday(rule, positions), bymonthday


def expand(rule_text, start):
    """按规则展开日期，输出严格递增、不重复。"""
    rule, positions = _parse_items(rule_text)
    freq, interval, count, until, byday, bymonthday = _validate(rule, positions)
    if freq == "DAILY":
        return _expand_daily(interval, count, until, byday, start)
    if freq == "WEEKLY":
        return _expand_weekly(interval, count, until, byday, start)
    return _expand_monthly(interval, count, until, bymonthday, start)


def _expand_daily(interval, count, until, byday, start):
    if byday and interval % 7 == 0 and WEEKDAYS[start.weekday()] not in byday:
        return []  # 步长整周时星期几固定，永远匹配不上
    out = []
    step = timedelta(days=interval)
    current = start
    while count is None or len(out) < count:
        if until is not None and current > until:
            break
        if not byday or WEEKDAYS[current.weekday()] in byday:
            out.append(current)
        current += step
    return out


def _expand_weekly(interval, count, until, byday, start):
    offsets = [WEEKDAYS.index(name) for name in byday] if byday else [start.weekday()]
    # 锚周：第一个含有 >= start 的匹配日的周（起始日所在周有匹配时就是第 0 周）
    first = min(start + timedelta(days=(offset - start.weekday()) % 7) for offset in offsets)
    anchor_monday = first - timedelta(days=first.weekday())
    out = []
    week = 0
    while count is None or len(out) < count:
        monday = anchor_monday + timedelta(weeks=week * interval)
        for offset in offsets:
            candidate = monday + timedelta(days=offset)
            if candidate < start:
                continue
            if until is not None and candidate > until:
                return out
            out.append(candidate)
            if count is not None and len(out) >= count:
                break
        week += 1
    return out


def _expand_monthly(interval, count, until, bymonthday, start):
    day = bymonthday or start.day
    origin = start.year * 12 + start.month - 1
    out = []
    month_index = 0
    while count is None or len(out) < count:
        total = origin + month_index * interval
        year, month = divmod(total, 12)
        month += 1
        month_index += 1
        if day > calendar.monthrange(year, month)[1]:
            continue  # 这个自然月没有这一天，跳过
        candidate = date(year, month, day)
        if candidate < start:
            continue
        if until is not None and candidate > until:
            break
        out.append(candidate)
    return out

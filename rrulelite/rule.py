"""重复规则展开（RFC 5545 子集）。只用标准库。

口径：
- WEEKLY 以起始日所在周（起始日起算的 7 天块）为第 0 周，每 INTERVAL 周取一周；
  同一周内命中的多个星期几按时间先后给出。
- DAILY 每隔 INTERVAL 天取一天，INTERVAL > 1 时直接按步长跳，不逐天空转。
- MONTHLY 按自然月推进（INTERVAL 个月一步），只保留真实存在的日期；
  BYMONTHDAY 指定每月第几天，缺省时用起始日的日号。
- BYDAY 按周一..周日排序去重；BYMONTHDAY 升序去重；两者在其他 FREQ 下作为过滤条件。
- 起始日符合规则时包含在结果里；UNTIL 含当天；COUNT 是最终条数。
"""

from datetime import date, timedelta

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

_FREQS = ("DAILY", "WEEKLY", "MONTHLY")
_KNOWN_KEYS = ("FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "COUNT", "UNTIL")
_DEFAULT_COUNT = 10


class RuleError(ValueError):
    """规则不合法；消息里指出是第几项。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def parse_rule(text):
    """解析 "FREQ=WEEKLY;COUNT=5" 为 dict（键大写，后者覆盖前者）。校验在 expand 里做。"""
    rule = {}
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        key, _, value = item.partition("=")
        rule[key.strip().upper()] = value.strip()
    return rule


def parse_date(text):
    """解析 YYYY-MM-DD，格式不对抛 RuleError。"""
    try:
        year, month, day = text.split("-")
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        raise RuleError("日期格式应为 YYYY-MM-DD：%r" % (text,))


def _parse_items(text):
    """切成 (键, 值, 第几项, 是否带等号)，跳过空项。"""
    items = []
    for raw in text.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        key, sep, value = raw.partition("=")
        items.append((key.strip().upper(), value.strip(), len(items) + 1, bool(sep)))
    return items


def _validate(rule_text):
    """解析并校验规则，返回 (freq, interval, count, until, byday, bymonthday)。

    byday 是排序去重后的星期序号列表（0=周一），None 表示未指定；
    bymonthday 是排序去重后的日号列表，None 表示未指定。
    """
    values = {}
    for key, value, index, has_eq in _parse_items(rule_text):
        if key not in _KNOWN_KEYS:
            raise RuleError("第 %d 项：未知键 %r" % (index, key))
        if not has_eq or not value:
            raise RuleError("第 %d 项：%s 缺值" % (index, key))
        values[key] = (value, index)

    freq = "DAILY"
    if "FREQ" in values:
        value, index = values["FREQ"]
        freq = value.upper()
        if freq not in _FREQS:
            raise RuleError(
                "第 %d 项：FREQ 只认 DAILY/WEEKLY/MONTHLY，得到 %r" % (index, value)
            )

    interval = 1
    if "INTERVAL" in values:
        value, index = values["INTERVAL"]
        try:
            interval = int(value)
        except ValueError:
            interval = 0
        if interval < 1:
            raise RuleError(
                "第 %d 项：INTERVAL 必须是 >= 1 的正整数，得到 %r" % (index, value)
            )

    count = _DEFAULT_COUNT
    if "COUNT" in values:
        value, index = values["COUNT"]
        try:
            count = int(value)
        except ValueError:
            count = -1
        if count < 0:
            raise RuleError(
                "第 %d 项：COUNT 必须是非负整数，得到 %r" % (index, value)
            )

    until = None
    if "UNTIL" in values:
        value, index = values["UNTIL"]
        try:
            until = parse_date(value)
        except RuleError:
            raise RuleError(
                "第 %d 项：UNTIL 日期格式应为 YYYY-MM-DD，得到 %r" % (index, value)
            )

    byday = None
    if "BYDAY" in values:
        value, index = values["BYDAY"]
        names = [part.strip().upper() for part in value.split(",") if part.strip()]
        if not names or any(name not in WEEKDAYS for name in names):
            raise RuleError(
                "第 %d 项：BYDAY 含非法星期名，得到 %r" % (index, value)
            )
        byday = sorted({WEEKDAYS.index(name) for name in names})

    bymonthday = None
    if "BYMONTHDAY" in values:
        value, index = values["BYMONTHDAY"]
        parts = [part.strip() for part in value.split(",") if part.strip()]
        days = []
        for part in parts:
            try:
                day = int(part)
            except ValueError:
                day = 0
            if not 1 <= day <= 31:
                days = []
                break
            days.append(day)
        if not days:
            raise RuleError(
                "第 %d 项：BYMONTHDAY 必须在 1..31，得到 %r" % (index, value)
            )
        bymonthday = sorted(set(days))

    return freq, interval, count, until, byday, bymonthday


def _matches(day, byday, bymonthday):
    if byday is not None and day.weekday() not in byday:
        return False
    if bymonthday is not None and day.day not in bymonthday:
        return False
    return True


def _expand_daily(start, interval, count, until, byday, bymonthday):
    out = []
    current = start
    step = timedelta(days=interval)
    while len(out) < count:
        if until is not None and current > until:
            break
        if _matches(current, byday, bymonthday):
            out.append(current)
        current += step
    return out


def _expand_weekly(start, interval, count, until, byday, bymonthday):
    weekdays = byday if byday is not None else [start.weekday()]
    out = []
    block = 0
    week = timedelta(days=7)
    while len(out) < count:
        block_start = start + block * week
        if until is not None and block_start > until:
            break
        if block % interval == 0:
            base = block_start.weekday()
            candidates = sorted(
                block_start + timedelta(days=(wd - base) % 7) for wd in weekdays
            )
            for candidate in candidates:
                if until is not None and candidate > until:
                    break
                if _matches(candidate, None, bymonthday):
                    out.append(candidate)
                    if len(out) >= count:
                        break
        block += 1
    return out


def _expand_monthly(start, interval, count, until, byday, bymonthday):
    monthdays = bymonthday if bymonthday is not None else [start.day]
    out = []
    year, month = start.year, start.month
    index = 0
    while len(out) < count:
        if until is not None and date(year, month, 1) > until:
            break
        if index % interval == 0:
            for monthday in monthdays:
                try:
                    candidate = date(year, month, monthday)
                except ValueError:
                    continue  # 这个月没有这一天，跳过
                if candidate < start:
                    continue
                if until is not None and candidate > until:
                    break
                if not _matches(candidate, byday, None):
                    continue
                out.append(candidate)
                if len(out) >= count:
                    break
        index += 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


def expand(rule_text, start):
    """按规则展开日期，返回严格递增、不重复的 date 列表。"""
    freq, interval, count, until, byday, bymonthday = _validate(rule_text)
    if freq == "DAILY":
        return _expand_daily(start, interval, count, until, byday, bymonthday)
    if freq == "WEEKLY":
        return _expand_weekly(start, interval, count, until, byday, bymonthday)
    return _expand_monthly(start, interval, count, until, byday, bymonthday)

"""重复规则展开。只用标准库。缺陷：WEEKLY 忽略 INTERVAL，MONTHLY 加 30 天，BYDAY 不排序。"""

from datetime import date, timedelta

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


class RuleError(ValueError):
    """规则不合法。缺陷：不带位置。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def parse_rule(text):
    """解析 "FREQ=WEEKLY;COUNT=5"。缺陷：键值都不校验。"""
    rule = {}
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        key, _, value = item.partition("=")
        rule[key.strip().upper()] = value.strip()
    return rule


def parse_date(text):
    """解析 YYYY-MM-DD。缺陷：格式不对时抛 Python 原始异常。"""
    year, month, day = text.split("-")
    return date(int(year), int(month), int(day))


def _byday(rule):
    raw = rule.get("BYDAY", "")
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def expand(rule_text, start):
    """缺陷：WEEKLY 固定每周推进，MONTHLY 每次加 30 天，BYDAY 按写法顺序输出。"""
    rule = parse_rule(rule_text)
    freq = rule.get("FREQ", "DAILY").upper()
    interval = int(rule.get("INTERVAL", "1"))
    count = int(rule.get("COUNT", "10"))
    until = parse_date(rule["UNTIL"]) if "UNTIL" in rule else None
    byday = _byday(rule)

    out = []
    if freq == "DAILY":
        current = start
        while len(out) < count:
            if not byday or WEEKDAYS[current.weekday()] in byday:
                out.append(current)
            current += timedelta(days=interval)
    elif freq == "WEEKLY":
        current = start
        while len(out) < count:
            for name in byday or [WEEKDAYS[current.weekday()]]:
                offset = WEEKDAYS.index(name) - current.weekday()
                candidate = current + timedelta(days=offset)
                if candidate < start:
                    continue
                out.append(candidate)
                if len(out) >= count:
                    break
            # 缺陷：INTERVAL 完全没用上，永远一周一周地走
            current += timedelta(days=7)
    elif freq == "MONTHLY":
        current = start
        while len(out) < count:
            # 缺陷：不看 BYMONTHDAY，也不按自然月推进，直接加 30 天
            out.append(current)
            current += timedelta(days=30)
    if until is not None:
        out = [day for day in out if day <= until]
    return out

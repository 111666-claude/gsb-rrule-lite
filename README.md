# rrule-lite

重复规则展开（RFC 5545 子集：FREQ / INTERVAL / BYDAY / BYMONTHDAY / COUNT / UNTIL），只用 Python 标准库。

```
python3 -m rrulelite.cli --rule 'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4' --start 2026-01-01
python3 -m rrulelite.cli --rule 'FREQ=MONTHLY;BYMONTHDAY=31;COUNT=3' --start 2026-01-31
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **WEEKLY 要按 INTERVAL 隔周**：`FREQ=WEEKLY;INTERVAL=2;BYDAY=MO;COUNT=4` 从 `2026-01-01`（周四）起
  按口径是 `01-05, 01-19, 02-02, 02-16`；现在 INTERVAL 被忽略，给每周一 `01-05, 01-12, 01-19, 01-26`。
- **MONTHLY 按自然月推进**：`FREQ=MONTHLY;BYMONTHDAY=31;COUNT=3` 从 `2026-01-31` 起按口径是
  `01-31, 03-31, 05-31`（2 月与 4 月没有 31 日就跳过）；现在每次加 30 天，给 `01-31, 03-02, 04-01`。
- **BYDAY 要排序去重**：`FREQ=WEEKLY;BYDAY=WE,MO;COUNT=4` 从 `2026-01-05` 起按口径是
  `01-05, 01-07, 01-12, 01-14`；现在按写法顺序输出 `WE` 在前，结果不递增。
- 起始日符合规则时要包含；`UNTIL` 含当天；`COUNT` 是最终条数（被 `UNTIL` 截断时可以少于 `COUNT`）。
- 校验：`FREQ` 只认 `DAILY`/`WEEKLY`/`MONTHLY`；未知键、缺值、`INTERVAL` 非正整数、`BYMONTHDAY` 不在 1..31、
  `BYDAY` 里有非法星期名都要报错并指出是第几项。
- 不变量：输出严格递增、不重复、每条都满足规则；同一规则重复展开结果相同。
- 规模：`COUNT ≤ 5000` 要在 0.1 秒内给出；`DAILY` 的 `INTERVAL > 1` 时不许一天一天空转，内存 O(输出)。
- 对照自证：小跨度输入与「逐日扫描再过滤」的参考实现逐项一致。

## 现在的行为

- `expand` 的 `WEEKLY` 分支固定 `current += timedelta(days=7)`，`INTERVAL` 完全没用上。
- `MONTHLY` 分支每次 `current += timedelta(days=30)`：日期会漂移，`BYMONTHDAY` 也不看。
- `BYDAY` 按写法顺序输出，`WE,MO` 就先给周三再给周一，结果不是递增的。
- `FREQ` 写错时既不报错也不产出（悄悄给空结果）；`parse_date` 抛的是 Python 原始异常。

## 计划新增的能力

```
--rule 规则     FREQ=...;INTERVAL=...;BYDAY=...;COUNT=...
--start 起始日  YYYY-MM-DD
```

## 输出

```
2026-01-05
2026-01-19
2026-02-02
2026-02-16
```

## 目录

```
rrulelite/rule.py   解析与展开
rrulelite/cli.py    命令行入口
tests/              unittest 用例
```

---
name: 开发反馈
description: 本项目积累的开发偏好、注意事项与已踩过的坑
type: feedback
---

## Barra VALUE 因子是低估值，不是"好公司"
VALUE 因子高 = 低PE/低PB；茅台等高PE白酒的 VALUE 因子为负，重仓茅台的基金会被打成"成长"而非"价值"——这是正确结果。
**Why:** 容易误以为 VALUE 高 = 基本面好，导致标签验证时误判。
**How to apply:** 验证风格标签结果时，不要用"好公司 = 价值"的直觉，以估值水平判断。

## numpy np.where 不能混用 float/str
新版 numpy 在 `np.where(cond, np.nan, '字符串')` 时抛 DTypePromotionError。
**Why:** numpy 无法为 float64 和 str 找到公共 dtype。
**How to apply:** 先赋字符串标签，再用 `.loc[mask, col] = None` 单独置空。

## 因子日期对齐用 tb_trade_calendar.c_max_trade_date
报告期（06-30/12-31）不一定是交易日（如 2024-06-30 是周日）。
**Why:** tb_stk_risk_factor / tb_stk_barra_status 只有交易日数据。
**How to apply:** `SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = :report_date`，同 tb_fd_ind_weight 的做法。

## 港股基金的动量/盈利/质量标签置 None
`c_region_tag='港股'` 的基金，这三个标签不打，即使有部分A股持仓也不算。
**Why:** 用户明确要求，港股风格基金的A股因子不具代表性。
**How to apply:** `result.loc[~non_hk | score.isna(), tag_col] = np.nan`。

## 季报期复用：generate_report_dates 过滤半年报
Q1/Q3 与相邻的 Q2/Q4 可能共享同一个4期半年报窗口，重复计算结果一致，UNIQUE KEY 覆盖写入即可，不需要特殊处理。
**Why:** 用户确认这个逻辑可以接受，简单直接。

## SPEC.md 定位：取数优先，不写 ETL 细节
SPEC 服务于取数场景（query skill → SQL），只需：字段清单 / 枚举值 / 注意事项（易踩的坑）/ 使用示例。计算型表加一行"依赖表：xxx/xxx"供追溯用。
**不写**：Oracle JOIN 条件、计算步骤、下游依赖、历史补数命令 → 放 insert.py 注释。
**Why:** 用户确认：取数时不关心 Oracle 视图，计算细节在 insert.py 里。
**How to apply:** 新建或修改 SPEC 时，遇到"数据来源/计算逻辑详细步骤"章节，精简为一行依赖表。

## 持仓查询按 c_style 分组，无需去重
全持仓用 `c_style IN ('02', '04')`，前十大用 `c_style IN ('01', '03', '05', '06')`，两组互斥，同一 report_date 内不存在重复行。
**Why:** 06-30/12-31 虽有两次披露（如 05 二季报 + 02 半年报），但只要按用途选对 c_style 分组，就不会出现同一(fd, stk, report_date)多条数据的情况，不需要 sort+drop_duplicates 兜底去重。
**How to apply:** 查询时直接用正确的 c_style 过滤条件，禁止混查两组后再去重。

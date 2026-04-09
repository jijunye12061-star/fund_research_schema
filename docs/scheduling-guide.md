# 调度与补数指南

> DAG 层级和表完整清单见 [table-catalog.md](table-catalog.md)。
> 本文档聚焦：调度时间线、补数起始日期规则、should_run 机制、标准 `__main__` 模板。

---

## 一、调度时间线

### 日频（每个交易日）

```
tb_stk_industry, tb_stk_concept, tb_fd_perform_abs
```

DS 以当天日期 `'YYYYMMDD'` 调用，`run()` 内部跳过非交易日。

---

### 季报披露后（报告期末 + 15 工作日）

| 报告期 | 大约触发时间 |
|--------|-------------|
| 03-31（一季报） | 约 4/22 |
| 06-30（二季报重仓） | 约 7/22 |
| 09-30（三季报） | 约 10/22 |
| 12-31（四季报重仓） | 约次年 1/22 |

**执行顺序：**

```
第 1 步（可并行）：
  tb_fd_category

第 2 步（依赖 tb_fd_category，可并行）：
  tb_fd_tag_asset
  tb_fd_tag_bd_style
  tb_fd_tag_stk_region_sector   ← 板块字段前向填充上期半年报数据

第 3 步（依赖第 2 步）：
  tb_fd_tag_stk_style           ← 季报期内部跳过（仅用半年报因子），前向填充
  tb_fd_tag_stk_portfolio       ← 重仓交易/top10 字段更新；集中度/换手率/抱团等前向填充
```

---

### 半年报 / 年报全量披露后

| 报告期 | c_style | 大约触发时间 |
|--------|---------|-------------|
| 06-30（半年报） | 02 | 报告期 + 60 自然日，约 8/29 |
| 12-31（年报） | 04 | 报告期 + 90 自然日，约次年 3/31 |

**执行顺序：**

```
第 1 步（可并行，依赖全持仓 c_style='02'/'04'）：
  tb_fd_ind_weight
  tb_fd_turnover
  tb_fd_bd_risk_metric

第 2 步（依赖第 1 步）：
  tb_stk_crowding_score

第 3 步（覆盖重跑，UNIQUE KEY 写入，半年报级字段正式计算）：
  tb_fd_tag_stk_style
  tb_fd_tag_stk_portfolio       ← should_run 判断 SEMI_ANNUAL，全字段更新
```

---

### 按需 / 低频

```
tb_fd_basic_info, tb_stk_basic_info, tb_stk_basic_info_hk,
tb_stk_industry_hk, tb_dict_params
```

全量同步，数据变更时手动触发。

---

## 二、补数起始日期规则

核心约束：Barra 因子从 2015 年起可用；标签需上游至少 2 年历史数据。

**约定：中间层半年度表统一 2015-06-30；标签层统一 2016-12-31。**

| 层 | 表名 | 频率 | 补数起点 | 期数 |
|---|------|------|----------|------|
| 日频 | tb_stk_industry / tb_stk_concept / tb_fd_perform_abs | 日频 | 2015-01-05 | — |
| 中间层-季度 | tb_fd_category | 季度 | 2015-03-31 | 44 期 |
| 中间层-半年度 | tb_fd_ind_weight | 半年度 | 2015-06-30 | 22 期 |
| 中间层-半年度 | tb_fd_turnover | 半年度 | 2015-06-30 | 22 期 |
| 中间层-半年度 | tb_fd_bd_risk_metric | 半年度 | 2015-06-30 | 22 期 |
| 中间层-半年度 | tb_stk_crowding_score | 半年度 | 2015-06-30 | 22 期 |
| 标签层（全部） | tb_fd_tag_asset / tb_fd_tag_bd_style / tb_fd_tag_stk_region_sector / tb_fd_tag_stk_style / tb_fd_tag_stk_portfolio | 综合 | **2016-12-31** | — |

---

## 三、should_run 机制（DS 调度标准模式）

`should_run(calc_date, freq)` 是所有季度/半年度表的标准 DS 调度入口。DS 每天以当天日期调用，函数判断"今天是否落在该频率的披露窗口内"，返回 `(True, report_date)` 或 `(False, '')`。

```python
from utils.common import should_run, ReportFreq

# 季度表标准 DS 入口
ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
if ok:
    run(report_date)

# 半年度表标准 DS 入口
ok, report_date = should_run(calc_date, ReportFreq.SEMI_ANNUAL)
if ok:
    run(report_date)
```

**新建表时直接套用**：确定表的更新频率后，DS 入口用对应的 `ReportFreq` 即可，无需手动计算报告期。

### 双触发表

`tb_fd_tag_stk_region_sector` 和 `tb_fd_tag_stk_portfolio` 同一报告期需触发两次：季报数据到了先跑一次（部分字段），中报/年报数据到了再覆盖重跑（全字段）。DS 入口依次判断两种频率：

```python
ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
if not ok:
    ok, report_date = should_run(calc_date, ReportFreq.SEMI_ANNUAL)
if ok:
    run(report_date)
```

其他表只有一种更新频率，只需判断一次。

---

## 四、标准 `__main__` 模板

### 季度表（DS 调度 + 补数）

```python
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        # DS 调度入口
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
        if ok:
            run(report_date)
    else:
        # 历史补数
        hist_dates = generate_report_dates('2025-12-31', N)  # N = 目标期数
        for dt in hist_dates:
            run(dt)
```

> **规范**：`run()` 统一接受 `report_date`，日期转换由 `should_run` 负责，`run()` 内部不做转换。

### 半年度表（DS 调度 + 补数）

```python
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.SEMI_ANNUAL)
        if ok:
            run(report_date)
    else:
        # 历史补数：只取半年报期（偶数索引）
        hist_dates = generate_report_dates('2025-12-31', N * 2)[::2]
        for dt in hist_dates:
            run(dt)
```

### 日频表

```python
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        run(f'{raw[:4]}-{raw[4:6]}-{raw[6:]}')
    else:
        run('2026-04-09')  # 单日手动触发，无补数循环
```

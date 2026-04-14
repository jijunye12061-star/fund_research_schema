# tb_stk_crowding_score — 个股抱团度得分表

## 概述

计算全市场权益基金及各基金公司对每只A股的抱团度得分，供 `tb_fd_tag_stk_portfolio` 加权聚合至基金维度。

- **KEY**: `(c_report_date, c_company_code, c_stk_code)`
- **计算频率**: 半年报期（06-30 / 12-31），DS 调度
- **股票范围**: A股（6位代码）
- **依赖表**: `tb_fd_portfolio_stk` / `tb_fd_category` / `tb_fd_basic_info`

---

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_report_date` | DATE | 报告期（06-30 / 12-31） |
| `c_company_code` | VARCHAR(20) | 基金公司代码；`MKT` = 全市场 |
| `c_stk_code` | VARCHAR(20) | 股票代码 |
| `c_total_hold_mv` | DECIMAL(20,4) | 该口径下持仓市值合计（元） |
| `c_crowd_score` | DECIMAL(10,4) | 该口径内百分位排名（0~1） |

---

## 注意事项

- **广义权益基金范围**：主动权益（c_type2_code='001001'）+ 全部混合型（c_type1_code='004'）；已做主代码去重
- `c_company_code = 'MKT'` 为全市场口径，其余为基金公司内部口径
- 得分为**口径内**百分位排名（0~1），全市场与公司口径不可直接比较
- 仅半年报期（06-30 / 12-31）有数据；查询时按 `c_report_date = :date` 精确查

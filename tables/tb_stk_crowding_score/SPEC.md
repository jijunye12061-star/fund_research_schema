# tb_stk_crowding_score — 个股抱团度得分表

## 概述

计算全市场权益基金及各基金公司对每只A股的抱团度得分，供 `tb_fd_tag_stk_portfolio` 加权聚合至基金维度。

- **KEY**: `(c_report_date, c_company_code, c_stk_code)`
- **计算频率**: 半年报期（06-30 / 12-31），DS 调度
- **股票范围**: A股（6位代码）

---

## 数据依赖

| 上游 | 用途 |
|---|---|
| `tytdata.tb_fd_portfolio_stk` | 广义权益基金全持仓（c_style IN '02','04'） |
| `tytdata.tb_fd_category` | 基金分类（筛选广义权益基金） |
| `tytdata.tb_fd_basic_info` | 基金→公司代码映射（c_company_code） |

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

## 计算说明

### 广义权益基金范围

`c_type1_code IN ('001', '004')` — 权益基金 + 混合型基金。

### 每期计算流程

1. 筛选广义权益基金的半年报全持仓（c_style IN ('02','04')，同一(fd, stk)取最大市值去重，仅保留A股 LENGTH=6）
2. **全市场口径**（c_company_code = 'MKT'）：汇总全部持仓市值，按 c_total_hold_mv 做全市场百分位排名
3. **公司口径**（c_company_code = 公司代码）：按公司分组，各公司内部独立排名

### 得分含义

- 得分越接近 1：该股票在该口径下越受基金青睐（持仓市值越大）
- 全市场口径与公司口径的排名相互独立，不可直接比较

### 下游聚合（在 tb_fd_tag_stk_portfolio 中执行）

**全市场抱团度 `c_crowd_score`**:
```
WHERE c_company_code = 'MKT'
c_crowd_score_fund = SUM(c_crowd_score × c_hold_value) / SUM(c_hold_value)
```

**同公司抱团度 `c_crowd_internal_score`**:
```
WHERE c_company_code = 该基金所属公司
c_crowd_internal_score_fund = SUM(c_crowd_score × c_hold_value) / SUM(c_hold_value)
```

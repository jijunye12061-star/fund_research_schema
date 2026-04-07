# tb_stk_crowding_score — 个股抱团度得分表

## 概述

计算全市场权益基金对每只A股的抱团度得分，供 `tb_fd_tag_stk_portfolio` 加权聚合至基金维度。

- **KEY**: `(c_report_date, c_stk_code)`
- **计算频率**: 半年报期（06-30 / 12-31），DS 调度
- **股票范围**: A股（6位代码）

---

## 数据依赖

| 上游 | 用途 |
|---|---|
| `tytdata.tb_fd_portfolio_stk` | 广义权益基金全持仓（c_style IN '02','04'） |
| `tytdata.tb_fd_category` | 基金分类（筛选广义权益基金） |

---

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_report_date` | DATE | 报告期（06-30 / 12-31） |
| `c_stk_code` | VARCHAR(20) | 股票代码 |
| `c_total_hold_mv` | DECIMAL(20,4) | 全市场权益基金持仓市值合计（元） |
| `c_crowd_score_mkt` | DECIMAL(10,4) | 全市场抱团度得分（百分位排名，0~1） |

---

## 计算说明

### 广义权益基金范围

`c_type1_code IN ('001', '004')` — 权益基金 + 混合型基金，排除固收加和债券型。

### 全市场抱团度得分

1. 筛选广义权益基金的半年报全持仓（c_style IN ('02','04')，同一(fd, stk)取最大市值去重）
2. 对每只股票，汇总所有权益基金的持仓市值：`c_total_hold_mv = sum(c_hold_value)`
3. 在全市场范围内按 `c_total_hold_mv` 做百分位排名（升序，method='average'）→ `c_crowd_score_mkt`

得分越接近 1，表示该股票被权益基金持有市值越大、越受青睐。

### 基金级聚合（在 tb_fd_tag_stk_portfolio 中执行）

**全市场抱团度 `c_crowd_score`**:
```
c_crowd_score = sum(c_crowd_score_mkt × c_hold_value) / sum(c_hold_value)
```

**同公司抱团度 `c_crowd_internal_score`**:
1. 对每家公司，在公司旗下基金的持仓中按股票累计市值做百分位排名
2. 以持仓市值加权聚合至基金维度

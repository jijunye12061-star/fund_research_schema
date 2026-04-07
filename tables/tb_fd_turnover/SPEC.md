# tb_fd_turnover — 基金股票交易换手率表

## 概述

存储每只基金每个半年报期的股票买卖金额和换手率，供 `tb_fd_tag_stk_portfolio` 消费。

- **KEY**: `(c_report_date, c_fd_code)`
- **计算频率**: 半年报期（06-30 / 12-31），DS 调度
- **基金范围**: 全量（不筛选类型，portfolio 表消费时自行筛选）

---

## 数据依赖

| 上游 | 用途 |
|---|---|
| `TYTFUND.FUND_IV_STOCKTRADESUM` | Oracle 源：买入/卖出金额（STYLE=02中报/04年报） |
| `tytdata.tb_fd_asset_allocation` | Doris 视图：三期季度末股票投资市值（c_stk_total_mv = SIMVSUM） |

---

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_report_date` | DATE | 报告期（06-30=上半年 / 12-31=下半年） |
| `c_fd_code` | VARCHAR(20) | 基金代码 |
| `c_buy_amount` | DECIMAL(20,4) | 半年度买入股票成本（元） |
| `c_sell_amount` | DECIMAL(20,4) | 半年度卖出股票收入（元） |
| `c_avg_stk_mv` | DECIMAL(20,4) | 三期股票投资市值均值（元，分母） |
| `c_turnover_rate` | DECIMAL(10,4) | 半年度双边换手率（%） |

---

## 计算说明

### 半年度双边换手率

```
换手率 = (买入金额 + 卖出金额) / 三期股票市值均值 × 100
```

**H1（report_date = 06-30）**:
- 分子：STYLE='02' 的 SHARECOST + SELLSUM（直接取中报数据）
- 分母：avg(SIMVSUM at 上年12-31, 当年03-31, 当年06-30)

**H2（report_date = 12-31）**:
- 分子：STYLE='04'（年报全年）减去 STYLE='02'（中报H1）的差值
- 分母：avg(SIMVSUM at 当年06-30, 当年09-30, 当年12-31)

### 股票市值来源

使用 `tb_fd_asset_allocation.c_stk_total_mv`（对应 Oracle 的 SIMVSUM，纯股票投资市值合计），不含可转债等。查询时 `c_is_stat = -1` 取合并统计口径，同一期多条记录取 MAX。

### H2 缺失处理

若基金无 H1 数据（STYLE='02' 缺失），无法差分，该基金当期不写入。

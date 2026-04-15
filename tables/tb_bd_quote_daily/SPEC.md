# tb_bd_quote_daily - 债券日行情表

## 基本信息

- **自然键**: (c_trade_date, c_bd_code)
- **表类型**: Oracle 视图映射
- **数据实效**: 实时同步（日更）
- **数据量**: 极大（全量债券日频，全表 COUNT 超时，查询必须带 c_bd_code 或 c_trade_date 条件）

## 数据来源

- **Oracle 表**: `TYTFUND.BOND_TD_DAILY`
- **映射方式**: `CREATE VIEW` 直接映射
- **过滤条件**: `WHERE EISDEL = '0'`

## 字段清单

| 字段名 | Oracle 字段 | 类型 | 注释 |
|--------|------------|------|------|
| c_trade_date | TDATE | DATE | 交易日期 |
| c_bd_code | BONDCODE | VARCHAR2(20) | 债券代码（6位）|
| c_bd_inner_code | SECURITYVARIETYCODE | NVARCHAR2(20) | 债券内码，跨市场唯一，推荐作 JOIN 关联键 |
| c_bd_name | SNAME | VARCHAR2(50) | 债券简称 |
| c_net_open | COPEN | DECIMAL(15,10) | 开盘净价（元）|
| c_net_close | CCLOSE | DECIMAL(15,10) | 收盘净价（元）|
| c_net_high | CHIGH | DECIMAL(15,10) | 最高净价（元）|
| c_net_low | CLOW | DECIMAL(15,10) | 最低净价（元）|
| c_net_pre_close | LCCLOSE | DECIMAL(15,10) | 前收盘净价（元）|
| c_net_chg_rate | CCHGRATE | DECIMAL(15,10) | 净价涨跌幅（%）|
| c_full_open | FOPEN | DECIMAL(15,10) | 开盘全价（元）|
| c_full_close | FCLOSE | DECIMAL(15,10) | 收盘全价（元）|
| c_full_high | FHIGH | DECIMAL(15,10) | 最高全价（元）|
| c_full_low | FLOW | DECIMAL(15,10) | 最低全价（元）|
| c_full_avg | FAVG | DECIMAL(15,10) | 全价加权均价（元，成交量加权 VWAP）|
| c_full_pre_close | LFCLOSE | DECIMAL(15,10) | 前收盘全价（元）|
| c_volume | TVOL | DECIMAL(15,2) | 成交量（**单位不统一，见下方注意**）|
| c_amount | TVAL | DECIMAL(15,2) | 成交金额（元）|
| c_trade_num | TNUM | INT | 成交笔数 |
| c_ytm_close | CYTM | DECIMAL(15,10) | 收盘到期收益率（%）|
| c_ytm_chg | YCHG | DECIMAL(38,18) | 收益率涨跌（BP）|

## 重要说明

### 净价 vs 全价的市场差异

| 市场 | TEXCH | 报价惯例 | 本表净价字段 | 本表全价字段 |
|------|-------|---------|------------|------------|
| 上交所可转债 | CNSESH | **全价**挂牌 | NULL | ✅ 有效 |
| 深交所可转债 | CNSESZ | **全价**挂牌 | NULL | ✅ 有效 |
| 银行间债券 | CNIBEX | **净价**报价 | ✅ 有效 | ✅ 有效 |

> 对转债的所有分析，应使用全价字段（`c_full_close`、`c_full_open` 等）。净价字段仅对银行间普通债券有意义。

### c_volume 单位不统一

- **银行间（CNIBEX）**: 单位为**元**（面值）
- **沪深交易所（CNSESH/CNSESZ）**: 单位为**手**（1手=10张=1000元面值）

跨市场比较成交量时需换算；直接用 `c_amount`（成交金额）不受此影响。

### YTM 字段

`c_ytm_close` / `c_ytm_chg` 对银行间债券有效，对交易所转债为 NULL（交易所 CB 不以 YTM 报价）。

### 查询性能警告

源表极大，全表扫描会超时。**查询时必须带至少一个高基数过滤条件**：

```sql
-- ✅ 正确：带债券代码
WHERE c_bd_code = '113050' AND c_trade_date >= '2024-01-01'

-- ✅ 正确：带单日期（一天约 5 万~15 万条，性能可接受）
WHERE c_trade_date = '2025-12-31' AND c_bd_code IN (...)

-- ❌ 错误：全表 COUNT / MIN(date) / MAX(date) 会超时
SELECT COUNT(*) FROM tb_bd_quote_daily WHERE EISDEL = '0'
```

## 使用示例

```sql
-- 查某支转债近一年全价行情
SELECT c_trade_date, c_full_close, c_full_pre_close,
       (c_full_close - c_full_pre_close) / c_full_pre_close * 100 AS full_pct_chg,
       c_volume, c_amount
FROM tytdata.tb_bd_quote_daily
WHERE c_bd_code = '113050'
  AND c_trade_date >= '2024-01-01'
ORDER BY c_trade_date;

-- 通过内码 JOIN 基础信息，过滤出转债
SELECT q.c_trade_date, q.c_bd_code, q.c_full_close, q.c_amount
FROM tytdata.tb_bd_quote_daily q
JOIN tytdata.tb_bd_basic_info b ON q.c_bd_inner_code = b.c_bd_inner_code
WHERE q.c_trade_date = '2025-12-31'
  AND b.c_bd_type = '可转换债券'
ORDER BY q.c_amount DESC;
```

## 下游依赖

- `tb_fd_tag_cb_style`（Task 4）：在需要转债价格的场景下通过 `c_bd_inner_code` JOIN 使用

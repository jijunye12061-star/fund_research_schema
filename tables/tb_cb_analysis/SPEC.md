# tb_cb_analysis - 转债估值分析表

## 基本信息

- **自然键**: (c_trade_date, c_bd_code)（已验证无重复）
- **表类型**: Oracle 视图映射
- **数据实效**: 实时同步（日更，T+0 可见当日数据）
- **数据量**: ~1,100,650 条（1993 年至今全量）；2020 年后约 280,000 条/年

## 数据来源

- **Oracle 表**: `TYTFUND.BOND_DR_CBANALYSIS`
- **映射方式**: `CREATE VIEW` 直接映射
- **过滤条件**: `WHERE EISDEL = '0'`

## 字段清单

| 字段名 | Oracle 字段 | 类型 | 注释 | 覆盖率（2020+）|
|--------|------------|------|------|--------------|
| c_trade_date | TDATE | DATE | 交易日期 | 100% |
| c_bd_code | BONDCODE | VARCHAR(40) | 转债代码（6位） | 100% |
| c_bd_inner_code | SECURITYVARIETYCODE | VARCHAR(100) | 债券内码，跨市场唯一，推荐作 JOIN 关联键 | 100% |
| c_pure_bond_value | PUREBONDVALUE | DECIMAL(19,10) | 纯债价值（元），按无转股权利的纯债折现 | ~97% |
| c_conv_value | SWAPVALUE | DECIMAL(19,10) | 转换价值（元）= 正股价 × 100 / 转股价 | 100% |
| c_conv_prem_rate | SWAPOR | DECIMAL(19,10) | 转股溢价率（%）= (转债价 - 转换价值) / 转换价值 × 100 | 98% |
| c_straight_prem_rate | PUREBONDOR | DECIMAL(19,10) | 纯债溢价率（%）= (转债价 - 纯债价值) / 纯债价值 × 100 | ~97% |
| c_floor_prem_rate | FLOOROR | DECIMAL(19,10) | 平底溢价率（%）= (转换价值 - 纯债价值) / 纯债价值 × 100 | ~97% |
| c_bond_value | BOND_VALUE_CB | DECIMAL(19,10) | 转债理论价值（元），含期权价值的综合估值 | ~97% |
| c_bond_premium | BOND_PREMIUM_CB | DECIMAL(20,8) | 转债溢价额（元）= 转债市价 - 理论价值 | ~97% |
| c_bond_prem_rate | BOND_PREMRATIO_CB | DECIMAL(20,8) | 转债溢价率（%）= 转债溢价额 / 理论价值 × 100 | ~97% |
| c_conv_delta | SWAPD | DECIMAL(19,10) | 转股期权 Delta（0~100），值越高股性越强 | **~86%** |
| c_current_ytm | CURRENTYTM | DECIMAL(19,10) | 到期收益率（%），以转债整体为基准 | ~97% |

## 字段说明

### 三大溢价率的关系

```
平底溢价率 = (转换价值 - 纯债价值) / 纯债价值
           = 转股溢价率的"地板"参照

偏债型 CB: 转换价值 < 纯债价值 → 平底溢价率 < 0（偏债）
偏股型 CB: 转换价值 > 纯债价值 → 平底溢价率 > 0（偏股）
```

### c_conv_delta（Delta）

- Oracle 字段 `SWAPD`，非 `SWAPD%`，**单位是 0~100（而非 0~1）**
- ~14% NULL（2025 年），主要出现在：北交所转债（810xxx/404xxx 代码）、部分非标品种
- 与 `c_conv_prem_rate` 的关系：Delta 高 ↔ 转股溢价率低（两者方向相反）

### c_current_ytm（到期收益率）

- 范围：~0%~242%（极值对应濒临退市/违约转债），正常存续期在 0%~5%
- `PUREBONDYTM`（纯债 YTM）在源表中完全为 NULL，视图不包含该字段

### NULL 规律

`c_pure_bond_value` / `c_straight_prem_rate` / `c_floor_prem_rate` 三字段同进同出，NULL 原因：
1. 早期数据（2010 年前）未计算纯债价值
2. 非标准结构品种（如可交换债、特殊条款）

`c_conv_prem_rate` 的 2% NULL 主要出现在 `c_conv_value` = 0 的记录（正股已退市/停牌）。

## 使用示例

```sql
-- 查询某日全部转债估值（过滤 NULL，用于分位数计算）
SELECT c_bd_code, c_conv_prem_rate, c_straight_prem_rate, c_floor_prem_rate, c_conv_delta
FROM tytdata.tb_cb_analysis
WHERE c_trade_date = '2025-12-31'
  AND c_conv_prem_rate IS NOT NULL
  AND c_straight_prem_rate IS NOT NULL;

-- 计算某日转股溢价率全市场分位数（用于 tb_fd_tag_cb_style）
SELECT c_bd_code,
       c_conv_prem_rate,
       PERCENT_RANK() OVER (ORDER BY c_conv_prem_rate) AS conv_prem_pct
FROM tytdata.tb_cb_analysis
WHERE c_trade_date = '2025-12-31'
  AND c_conv_prem_rate IS NOT NULL;

-- 通过内码关联 tb_bd_basic_info 获取正股代码
SELECT a.c_trade_date, a.c_bd_code, b.c_stk_code, a.c_conv_prem_rate, a.c_conv_delta
FROM tytdata.tb_cb_analysis a
JOIN tytdata.tb_bd_basic_info b ON a.c_bd_inner_code = b.c_bd_inner_code
WHERE a.c_trade_date = '2025-12-31'
  AND b.c_bd_type = '可转换债券';
```

## 下游依赖

- `tb_fd_tag_cb_style`（Task 4）：取 `c_conv_prem_rate`、`c_straight_prem_rate`、`c_floor_prem_rate` 计算分位数，`c_conv_delta` 备用

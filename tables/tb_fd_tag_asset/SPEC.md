# tb_fd_tag_asset_eq - 权益基金资产配置标签表

## 基本信息

- **主键**: (c_fd_code, c_report_date)
- **更新频率**: 季度
- **适用范围**: `tb_fd_category.c_type1_code IN ('001')` 主动权益/指数增强/被动指数基金
- **依赖表**: `tb_fd_asset_allocation` / `tb_fd_category`

## 字段清单

| 字段名               | 类型           | 注释       | 说明           |
|-------------------|--------------|----------|--------------|
| c_fd_code         | VARCHAR(20)  | 基金代码     | 六位代码         |
| c_report_date     | DATE         | 报告期      | 季报截止日        |
| c_stk_pos_avg     | DECIMAL(8,4) | 股票仓位均值   | 近八期均值，单位：%   |
| c_stk_pos_chg_avg | DECIMAL(8,4) | 股票仓位变动均值 | 近八期变动均值，单位：% |
| c_stk_pos_level   | VARCHAR(20)  | 股票仓位等级   | 见枚举值         |
| c_stk_timing      | VARCHAR(10)  | 股票择时标签   | 见枚举值         |
| c_updatetime      | DATETIME(6)  | 更新时间     | 系统自动生成       |

## 枚举值

### 股票仓位等级 (c_stk_pos_level)

| 取值   | 判断逻辑        |
|------|-------------|
| 高仓位  | 股票仓位均值 ≥90% |
| 中高仓位 | 股票仓位均值 <90% |

### 股票择时标签 (c_stk_timing)

| 取值  | 判断逻辑       |
|-----|------------|
| 择时  | 仓位变动均值 ≥5% |
| 不择时 | 仓位变动均值 <5% |

## 使用示例

```sql
-- 查询某报告期权益基金仓位标签
SELECT c_fd_code, c_stk_pos_avg, c_stk_pos_level, c_stk_timing
FROM tytdata.tb_fd_tag_asset_eq
WHERE c_report_date = '2024-09-30'
  AND c_fd_code = '000001';
```

---

# tb_fd_tag_asset_fi - 固收+基金资产配置标签表

## 基本信息

- **主键**: (c_fd_code, c_report_date)
- **更新频率**: 季度
- **适用范围**: `tb_fd_category.c_type1_code IN ('002')` 固收+基金（可转债/混合债/偏债混合/灵活配置）
- **依赖表**: `tb_fd_asset_allocation` / `tb_fd_category`

## 字段清单

| 字段名               | 类型           | 注释       | 说明           |
|-------------------|--------------|----------|--------------|
| c_fd_code         | VARCHAR(20)  | 基金代码     | 六位代码         |
| c_report_date     | DATE         | 报告期      | 季报截止日        |
| c_stk_pos_avg     | DECIMAL(8,4) | 股票仓位均值   | 近八期均值，单位：%   |
| c_cb_pos_avg      | DECIMAL(8,4) | 转债仓位均值   | 近八期均值，单位：%   |
| c_eq_pos_avg      | DECIMAL(8,4) | 权益仓位均值   | 股票+转债/2，单位：% |
| c_stk_pos_chg_avg | DECIMAL(8,4) | 股票仓位变动均值 | 近八期变动均值，单位：% |
| c_cb_pos_chg_avg  | DECIMAL(8,4) | 转债仓位变动均值 | 近八期变动均值，单位：% |
| c_eq_risk_level   | VARCHAR(10)  | 风险特征标签   | 见枚举值         |
| c_stk_cb_strategy | VARCHAR(30)  | 股票转债策略标签 | 见枚举值         |
| c_stk_timing      | VARCHAR(10)  | 股票择时标签   | 见枚举值         |
| c_cb_timing       | VARCHAR(10)  | 转债择时标签   | 见枚举值         |
| c_updatetime      | DATETIME(6)  | 更新时间     | 系统自动生成       |

## 枚举值

### 风险特征标签 (c_eq_risk_level)

| 取值 | 判断逻辑           |
|----|----------------|
| 稳健 | 权益仓位均值 <15%    |
| 均衡 | 权益仓位均值 15%-25% |
| 激进 | 权益仓位均值 ≥25%    |

### 股票转债策略标签 (c_stk_cb_strategy)

| 取值       | 判断逻辑        |
|----------|-------------|
| 纯股票      | 转债仓位为0      |
| 股票为主转债为辅 | 转债/股票比值 <1  |
| 股票转债均衡   | 转债/股票比值 1-4 |
| 转债为主股票为辅 | 转债/股票比值 >4  |

### 择时标签 (c_stk_timing / c_cb_timing)

| 字段           | 取值     | 判断逻辑          |
|--------------|--------|---------------|
| c_stk_timing | 择时/不择时 | 变动均值 ≥5% 为择时  |
| c_cb_timing  | 择时/不择时 | 变动均值 ≥10% 为择时 |

## 使用示例

```sql
-- 查询激进型固收+基金
SELECT c_fd_code, c_eq_pos_avg, c_stk_cb_strategy
FROM tytdata.tb_fd_tag_asset_fi
WHERE c_report_date = '2024-09-30'
  AND c_eq_risk_level = '激进';
```

---

# tb_fd_tag_asset_mix - 混合基金资产配置标签表

## 基本信息

- **主键**: (c_fd_code, c_report_date)
- **更新频率**: 季度
- **适用范围**: `tb_fd_category.c_type1_code IN ('004')` 混合型基金（偏股/平衡/偏债/灵活配置）
- **依赖表**: `tb_fd_asset_allocation` / `tb_fd_category`

## 字段清单

| 字段名               | 类型           | 注释       | 说明           |
|-------------------|--------------|----------|--------------|
| c_fd_code         | VARCHAR(20)  | 基金代码     | 六位代码         |
| c_report_date     | DATE         | 报告期      | 季报截止日        |
| c_stk_pos_avg     | DECIMAL(8,4) | 股票仓位均值   | 近八期均值，单位：%   |
| c_cb_pos_avg      | DECIMAL(8,4) | 转债仓位均值   | 近八期均值，单位：%   |
| c_eq_pos_avg      | DECIMAL(8,4) | 权益仓位均值   | 股票+转债/2，单位：% |
| c_bd_pos_avg      | DECIMAL(8,4) | 债券仓位均值   | 近八期均值，单位：%   |
| c_stk_pos_chg_avg | DECIMAL(8,4) | 股票仓位变动均值 | 近八期变动均值，单位：% |
| c_cb_pos_chg_avg  | DECIMAL(8,4) | 转债仓位变动均值 | 近八期变动均值，单位：% |
| c_eq_pos_chg_avg  | DECIMAL(8,4) | 权益仓位变动均值 | 近八期变动均值，单位：% |
| c_stk_bd_pref     | VARCHAR(20)  | 股债偏好标签   | 见枚举值         |
| c_eq_strategy     | VARCHAR(30)  | 权益策略标签   | 见枚举值         |
| c_eq_timing       | VARCHAR(10)  | 权益择时标签   | 见枚举值         |
| c_stk_timing      | VARCHAR(10)  | 股票择时标签   | 见枚举值         |
| c_cb_timing       | VARCHAR(10)  | 转债择时标签   | 见枚举值         |
| c_updatetime      | DATETIME(6)  | 更新时间     | 系统自动生成       |

## 枚举值

### 股债偏好标签 (c_stk_bd_pref)

| 取值   | 判断逻辑          |
|------|---------------|
| 偏股   | 债券/股票比值 <0.5  |
| 股债均衡 | 债券/股票比值 0.5-2 |
| 偏债   | 债券/股票比值 >2    |

### 权益策略标签 (c_eq_strategy)

| 取值     | 判断逻辑        |
|--------|-------------|
| 纯股票    | 转债仓位为0      |
| 偏股票    | 转债/股票比值 <1  |
| 股票转债均衡 | 转债/股票比值 1-4 |
| 偏转债    | 转债/股票比值 >4  |

### 择时标签 (c_eq_timing / c_stk_timing / c_cb_timing)

| 字段           | 取值     | 判断逻辑          |
|--------------|--------|---------------|
| c_eq_timing  | 择时/不择时 | 变动均值 ≥5% 为择时  |
| c_stk_timing | 择时/不择时 | 变动均值 ≥5% 为择时  |
| c_cb_timing  | 择时/不择时 | 变动均值 ≥10% 为择时 |

## 使用示例

```sql
-- 查询偏股型混合基金
SELECT c_fd_code, c_stk_pos_avg, c_bd_pos_avg, c_eq_strategy
FROM tytdata.tb_fd_tag_asset_mix
WHERE c_report_date = '2024-09-30'
  AND c_stk_bd_pref = '偏股';
```
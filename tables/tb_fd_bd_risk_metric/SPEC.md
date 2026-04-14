# tb_fd_bd_risk_metric - 债券信用评级与久期指标表

## 基本信息

- **主键**: (c_report_date, c_fd_code)
- **更新频率**: 半年度
- **依赖表**: Oracle `FUND_IV_HOLDCREDITRISKO` / `FUND_IV_RISKSENSITIVE` / `FUND_IV_ASSETALLOCT`

## 字段清单

### 主键与控制字段

| 字段名           | 类型          | 注释   | 说明     |
|---------------|-------------|------|--------|
| c_report_date | DATE        | 报告日期 | 季报截止日  |
| c_fd_code     | VARCHAR(20) | 基金代码 | 六位代码   |
| c_updatetime  | DATETIME(6) | 更新时间 | 系统自动生成 |

### 信用评级明细

数据源: `TYTFUND.FUND_IV_HOLDCREDITRISKO`，过滤 `INVEST_TYPE='1'`(债券) `EISDEL='0'`

**短期信用评级 (RATETYPE=100)**

| 字段名                | 类型            | 注释                 | RATING |
|--------------------|---------------|--------------------|--------|
| c_short_high_mv    | DECIMAL(20,4) | 短期高评级(A-1)市值(万元)   | 101    |
| c_short_low_mv     | DECIMAL(20,4) | 短期低评级(A-1以下)市值(万元) | 102    |
| c_short_unrated_mv | DECIMAL(20,4) | 短期未评级市值(万元)        | 300    |

**长期信用评级 (RATETYPE=200)**

| 字段名               | 类型            | 注释                 | RATING |
|-------------------|---------------|--------------------|--------|
| c_long_high_mv    | DECIMAL(20,4) | 长期高评级(AAA)市值(万元)   | 201    |
| c_long_low_mv     | DECIMAL(20,4) | 长期低评级(AAA以下)市值(万元) | 202    |
| c_long_unrated_mv | DECIMAL(20,4) | 长期未评级市值(万元)        | 300    |

每类内: 高(101/201) + 低(102/202) + 未评级(300) = 合计(99)

**汇总占比 (短期+长期合并)**

| 字段名                    | 类型            | 注释         | 计算公式                         |
|------------------------|---------------|------------|------------------------------|
| c_high_credit_ratio    | DECIMAL(10,4) | 高信用评级占比(%) | (A-1 + AAA) / 全部合计 × 100     |
| c_low_credit_ratio     | DECIMAL(10,4) | 低信用评级占比(%) | (A-1以下 + AAA以下) / 全部合计 × 100 |
| c_unrated_credit_ratio | DECIMAL(10,4) | 未评级占比(%)   | (短期未评级 + 长期未评级) / 全部合计 × 100 |

> 全部合计 = 短期合计(RATETYPE=100,RATING=99) + 长期合计(RATETYPE=200,RATING=99)

### 久期

数据源: `TYTFUND.FUND_IV_RISKSENSITIVE`，过滤 `VARIABLERISKCODE='100101'` `EISDEL='0'`

原始数据包含利率**上升**和**下降**两个方向（CHANGEDIRECT）的模拟结果：假设利率变动 CHGRATIO，基金净值相应变动
FNVALUET。由于两个方向符号相反，计算久期时取净值变动的绝对值求和，再除以变动比例之和与债券市值。

| 字段名        | 类型            | 注释         | 说明                                              |
|------------|---------------|------------|-------------------------------------------------|
| c_bond_mv  | DECIMAL(20,4) | 债券投资市值(万元) | FUND_IV_ASSETALLOCT.BSUM                        |
| c_duration | DECIMAL(10,4) | 久期(年)      | SUM(ABS(FNVALUET)) / SUM(CHGRATIO) / BSUM × 100 |

## 注意事项

- 分母为0时（无RATING='99'合计行），该基金该期信用评级为NULL
- 久期依赖 `FUND_IV_ASSETALLOCT.BSUM`（JOIN条件: 同基金同报告期, STYLE IN ('01','02','03','04')）
- 信用评级和久期数据覆盖范围可能不同，outer merge保留所有可用数据
- 市值字段存原始值（万元），占比字段存百分数

## 使用示例

```sql
-- 查询某基金信用评级全貌
SELECT c_fd_code,
       c_short_high_mv,
       c_short_low_mv,
       c_short_unrated_mv,
       c_long_high_mv,
       c_long_low_mv,
       c_long_unrated_mv,
       c_high_credit_ratio,
       c_low_credit_ratio,
       c_unrated_credit_ratio
FROM tytdata.tb_fd_bd_risk_metric
WHERE c_report_date = '2024-06-30'
  AND c_fd_code = '000005';

-- 只看长期评级分布
SELECT c_fd_code,
       c_long_high_mv / NULLIF(c_long_high_mv + c_long_low_mv + c_long_unrated_mv, 0) * 100    AS long_high_pct,
       c_long_low_mv / NULLIF(c_long_high_mv + c_long_low_mv + c_long_unrated_mv, 0) * 100     AS long_low_pct,
       c_long_unrated_mv / NULLIF(c_long_high_mv + c_long_low_mv + c_long_unrated_mv, 0) * 100 AS long_unrated_pct
FROM tytdata.tb_fd_bd_risk_metric
WHERE c_report_date = '2024-06-30';
```

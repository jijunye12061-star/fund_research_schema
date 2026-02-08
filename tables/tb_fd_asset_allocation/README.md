# tb_fd_asset_allocation - 基金资产配置表

## 基本信息

- **主键**: (c_fd_code, c_report_date, c_style)
- **更新频率**: 季度
- **数据范围**: 基金季报资产配置明细

## 字段清单

### 基础信息

| 字段名                | 类型             | 注释     |
|--------------------|----------------|--------|
| c_fd_code          | VARCHAR(20)    | 基金代码   |
| c_report_date      | DATE           | 报告日期   |
| c_style            | VARCHAR(20)    | 报表类型   |
| c_notice_date      | DATE           | 公告日期   |
| c_fund_total_asset | DECIMAL(38,18) | 基金总资产  |
| c_fund_nav_total   | DECIMAL(38,18) | 基金净值总额 |

### 股票投资

| 字段名                   | 类型             | 注释         |
|-----------------------|----------------|------------|
| c_stk_total_mv        | DECIMAL(38,18) | 股票投资市值合计   |
| c_stk_total_ratio     | DECIMAL(38,18) | 股票投资占净值比例  |
| c_stk_index_mv        | DECIMAL(38,18) | 指数化投资市值    |
| c_stk_index_ratio     | DECIMAL(38,18) | 指数化投资占净值比例 |
| c_stk_active_mv       | DECIMAL(38,18) | 积极投资市值     |
| c_stk_active_ratio    | DECIMAL(38,18) | 积极投资占净值比例  |
| c_stk_equity_mv       | DECIMAL(18,2)  | 权益类投资市值    |
| c_stk_equity_ratio    | DECIMAL(18,2)  | 权益类投资占净值比例 |
| c_stk_preferred_mv    | DECIMAL(18,2)  | 优先股市值      |
| c_stk_preferred_ratio | DECIMAL(18,2)  | 优先股占净值比例   |

### 债券投资

| 字段名                     | 类型             | 注释           |
|-------------------------|----------------|--------------|
| c_bd_total_mv           | DECIMAL(38,18) | 债券市值合计       |
| c_bd_total_ratio        | DECIMAL(38,18) | 债券市值占净值比例    |
| c_bd_convertible_mv     | DECIMAL(38,18) | 可转换债券市值      |
| c_bd_convertible_ratio  | DECIMAL(38,18) | 可转债占净值比例     |
| c_bd_treasury_mv        | DECIMAL(38,18) | 国债市值         |
| c_bd_treasury_ratio     | DECIMAL(38,18) | 国债占净值比例      |
| c_bd_financial_mv       | DECIMAL(38,18) | 金融债市值        |
| c_bd_financial_ratio    | DECIMAL(38,18) | 金融债占净值比例     |
| c_bd_policy_mv          | DECIMAL(19,4)  | 政策性金融债市值     |
| c_bd_policy_ratio       | DECIMAL(9,4)   | 政策性金融债占净值比例  |
| c_bd_corporate_mv       | DECIMAL(38,18) | 企业债市值        |
| c_bd_corporate_ratio    | DECIMAL(38,18) | 企业债占净值比例     |
| c_bd_short_term_mv      | DECIMAL(19,4)  | 企业短期融资券市值    |
| c_bd_short_term_ratio   | DECIMAL(9,4)   | 企业短期融资券占净值比例 |
| c_bd_mtn_mv             | DECIMAL(18,2)  | 中期票据市值       |
| c_bd_mtn_ratio          | DECIMAL(18,2)  | 中期票据占净值比例    |
| c_bd_central_bank_mv    | DECIMAL(38,18) | 央行票据市值       |
| c_bd_central_bank_ratio | DECIMAL(38,18) | 央行票据占净值比例    |
| c_bd_deposit_cert_mv    | DECIMAL(20,8)  | 同业存单市值       |
| c_bd_deposit_cert_ratio | DECIMAL(20,8)  | 同业存单占净值比例    |
| c_bd_fixed_income_mv    | DECIMAL(38,18) | 固定收益类投资市值合计  |
| c_bd_fixed_income_ratio | DECIMAL(38,18) | 固定收益类投资占净值比例 |
| c_bd_other_mv           | DECIMAL(38,18) | 其他债券市值       |
| c_bd_other_ratio        | DECIMAL(38,18) | 其他债券占净值比例    |

### 现金货币

| 字段名                      | 类型             | 注释          |
|--------------------------|----------------|-------------|
| c_cash_total_mv          | DECIMAL(38,18) | 货币资金合计      |
| c_cash_total_ratio       | DECIMAL(38,18) | 货币资金占净值比例   |
| c_cash_deposit_mv        | DECIMAL(38,18) | 银行存款        |
| c_cash_deposit_ratio     | DECIMAL(38,18) | 银行存款占净值比例   |
| c_cash_market_tool_mv    | DECIMAL(19,4)  | 货币市场工具市值合计  |
| c_cash_market_tool_ratio | DECIMAL(9,4)   | 货币市场工具占净值比例 |
| c_cash_settlement_mv     | DECIMAL(38,18) | 清算备付金       |
| c_cash_settlement_ratio  | DECIMAL(38,18) | 清算备付金占净值比例  |

### 基金投资

| 字段名                  | 类型            | 注释          |
|----------------------|---------------|-------------|
| c_fd_inv_total_mv    | DECIMAL(19,4) | 基金投资市值合计    |
| c_fd_inv_total_ratio | DECIMAL(9,4)  | 基金投资市值占净值比例 |

### 衍生品投资

| 字段名                   | 类型            | 注释           |
|-----------------------|---------------|--------------|
| c_deriv_total_mv      | DECIMAL(19,4) | 金融衍生品投资      |
| c_deriv_total_ratio   | DECIMAL(9,4)  | 金融衍生品投资占净值比例 |
| c_deriv_forward_mv    | DECIMAL(19,4) | 远期投资市值       |
| c_deriv_forward_ratio | DECIMAL(9,4)  | 远期投资市值占净值比例  |
| c_deriv_future_mv     | DECIMAL(19,4) | 期货投资市值       |
| c_deriv_future_ratio  | DECIMAL(9,4)  | 期货投资市值占净值比例  |
| c_deriv_option_mv     | DECIMAL(19,4) | 期权投资市值       |
| c_deriv_option_ratio  | DECIMAL(9,4)  | 期权占净值比例      |

### 其他投资品种

| 字段名                       | 类型             | 注释              |
|---------------------------|----------------|-----------------|
| c_other_warrant_mv        | DECIMAL(19,4)  | 权证投资市值合计        |
| c_other_warrant_ratio     | DECIMAL(9,4)   | 权证投资市值占净值比例     |
| c_other_abs_mv            | DECIMAL(38,18) | 资产支持证券市值合计      |
| c_other_abs_ratio         | DECIMAL(38,18) | 资产支持证券市值占净值比例   |
| c_other_infra_abs_mv      | DECIMAL(38,18) | 基础设施资产支持证券市值    |
| c_other_infra_abs_ratio   | DECIMAL(38,18) | 基础设施资产支持证券占净值比例 |
| c_other_tdr_mv            | DECIMAL(19,4)  | 存托凭证市值合计        |
| c_other_tdr_ratio         | DECIMAL(9,4)   | 存托凭证占净值比例       |
| c_other_reits_mv          | DECIMAL(18,2)  | 房地产信托市值         |
| c_other_reits_ratio       | DECIMAL(18,2)  | 房地产信托市值占净值比例    |
| c_other_commodity_mv      | DECIMAL(18,2)  | 商品现货合约投资市值      |
| c_other_commodity_ratio   | DECIMAL(18,2)  | 商品现货合约投资占净值比例   |
| c_other_gold_mv           | DECIMAL(18,2)  | 黄金市值            |
| c_other_gold_ratio        | DECIMAL(18,2)  | 黄金占净值比例         |
| c_other_long_equity_mv    | DECIMAL(38,18) | 长期股权投资          |
| c_other_long_equity_ratio | DECIMAL(38,18) | 长期股权投资占净值比例     |

### 回购业务

| 字段名                     | 类型             | 注释               |
|-------------------------|----------------|------------------|
| c_repo_buy_resell_mv    | DECIMAL(38,18) | 买入返售金融资产         |
| c_repo_buy_resell_ratio | DECIMAL(38,18) | 买入返售证券占净值比例      |
| c_repo_sell_buy_mv      | DECIMAL(38,18) | 卖出回购证券余额         |
| c_repo_sell_buy_ratio   | DECIMAL(38,18) | 卖出回购证券占净值比例      |
| c_repo_buyout_mv        | DECIMAL(19,4)  | 买断式回购的买入返售金融资产   |
| c_repo_buyout_ratio     | DECIMAL(9,4)   | 买断式回购的买入返售金融资产比例 |

### 应收款项

| 字段名                    | 类型             | 注释           |
|------------------------|----------------|--------------|
| c_recv_sec_clear_mv    | DECIMAL(38,18) | 应收证券清算款      |
| c_recv_sec_clear_ratio | DECIMAL(38,18) | 应收证券清算款占净值比例 |
| c_recv_margin_mv       | DECIMAL(19,4)  | 交易保证金        |
| c_recv_margin_ratio    | DECIMAL(9,4)   | 交易保证金占净值比例   |
| c_recv_dividend_mv     | DECIMAL(19,4)  | 应收股利         |
| c_recv_dividend_ratio  | DECIMAL(9,4)   | 应收股利占净值比例    |
| c_recv_interest_mv     | DECIMAL(19,4)  | 应收利息         |
| c_recv_interest_ratio  | DECIMAL(9,4)   | 应收利息占净值比例    |
| c_recv_purchase_mv     | DECIMAL(19,4)  | 应收申购款        |
| c_recv_purchase_ratio  | DECIMAL(9,4)   | 应收申购款占净值比例   |

### 其他杂项

| 字段名                       | 类型             | 注释          |
|---------------------------|----------------|-------------|
| c_misc_debt_balance_mv    | DECIMAL(38,18) | 贷方余额        |
| c_misc_debt_balance_ratio | DECIMAL(38,18) | 贷方余额占净值比例   |
| c_misc_other_inv_mv       | DECIMAL(38,18) | 其他投资市值      |
| c_misc_other_inv_ratio    | DECIMAL(38,18) | 其他投资占净值比例   |
| c_misc_deferred_exp_mv    | DECIMAL(19,4)  | 待摊费用        |
| c_misc_deferred_exp_ratio | DECIMAL(9,4)   | 待摊费用占净值比例   |
| c_misc_other_recv_mv      | DECIMAL(19,4)  | 其他应收款       |
| c_misc_other_recv_ratio   | DECIMAL(9,4)   | 其他应收款占净值比例  |
| c_misc_other_asset_mv     | DECIMAL(18,2)  | 其他其他资产      |
| c_misc_other_asset_ratio  | DECIMAL(18,2)  | 其他其他资产占净值比例 |

### 控制字段

| 字段名          | 类型          | 注释               |
|--------------|-------------|------------------|
| c_is_stat    | TINYINT     | 是否参与统计(-1主0分级)   |
| c_is_sum     | TINYINT     | 是否为合并数据(1为是,0为否) |
| c_updatetime | DATETIME(6) | 更新时间             |

## 枚举值

### 报表类型 (c_style)

| 代码 | 名称  | 说明  |
|----|-----|-----|
| 01 | 一季报 | Q1  |
| 02 | 中报  | 半年报 |
| 03 | 三季报 | Q3  |
| 04 | 年报  | 全年  |
| 05 | 二季报 | Q2  |
| 06 | 四季报 | Q4  |
| 07 | 其他  | 特殊  |

## 使用示例

```sql
-- 查询某基金最新季报资产配置
SELECT c_fd_code,
       c_report_date,
       c_stk_total_ratio,
       c_bd_total_ratio,
       c_cash_total_ratio
FROM tytdata.tb_fd_asset_allocation
WHERE c_fd_code = '000001'
  AND c_report_date = '2024-06-30'
  AND c_style = '02'
```
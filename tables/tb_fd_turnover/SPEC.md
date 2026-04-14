# tb_fd_turnover — 基金股票交易换手率表

## 概述

存储每只基金每个半年报期的股票买卖金额和换手率，供 `tb_fd_tag_stk_portfolio` 消费。

- **KEY**: `(c_report_date, c_fd_code)`
- **计算频率**: 半年报期（06-30 / 12-31），DS 调度
- **基金范围**: 全量（不筛选类型，portfolio 表消费时自行筛选）
- **依赖表**: Oracle `FUND_IV_STOCKTRADESUM` / `tb_fd_asset_allocation`

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

## 注意事项

- `c_turnover_rate` 为 NULL 时表示该期股票仓位极低（c_avg_stk_mv < 100万），属过渡态/清盘期，无业务含义
- 公式：`(买入金额 + 卖出金额) / 三期股票市值均值 × 100`；H2（12-31）为年报全年减去中报H1的差分
- 若基金无中报（STYLE='02'）数据，该基金当期不写入，查询时可能出现年末缺失

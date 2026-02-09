# tb_fd_nav_daily - 基金净值日数据表

## 基本信息

- **主键**: (c_fd_code, c_trade_date)
- **表类型**: Oracle视图映射
- **数据实效**: 实时同步

## 数据来源

- **Oracle表**:
    - TYTFUND.FUND_DR_FUNDNV（主表 - 基金净值数据）
    - TYTFUND.QT_TRADE_CALENDAR（交易日历）
- **映射方式**: CREATE VIEW + LEFT JOIN
- **过滤条件**: WHERE EISDEL = '0'
- **关联逻辑**: 净值日期关联交易日历判断是否交易日

## 字段清单

| 字段名               | 类型            | 注释           | 说明    |
|-------------------|---------------|--------------|-------|
| c_trade_date      | DATE          | 交易日          | -     |
| c_fd_code         | VARCHAR(20)   | 基金代码         | 六位代码  |
| c_nav             | DECIMAL(20,8) | 单位净值         | 元     |
| c_nav_acc         | DECIMAL(20,8) | 累计单位净值       | 元     |
| c_nav_adj         | DECIMAL(20,8) | 复权单位净值       | 元     |
| c_nav_adj_pre     | DECIMAL(20,8) | 昨复权单位净值      | 元     |
| c_ret_tw          | DECIMAL(20,8) | 本周净值增长率      | %     |
| c_ret_tm          | DECIMAL(20,8) | 本月净值增长率      | %     |
| c_ret_adj_estab   | DECIMAL(20,8) | 成立至今复权净值增长率  | %     |
| c_ret_estab       | DECIMAL(20,8) | 成立至今净值增长率    | %     |
| c_ret_ann         | DECIMAL(20,8) | 年化总回报        | %     |
| c_ret_1w          | DECIMAL(20,8) | 最近1周净值增长率    | %     |
| c_ret_1m          | DECIMAL(20,8) | 最近1月净值增长率    | %     |
| c_ret_3m          | DECIMAL(20,8) | 最近3月净值增长率    | %     |
| c_ret_6m          | DECIMAL(20,8) | 最近6月净值增长率    | %     |
| c_ret_1y          | DECIMAL(20,8) | 最近1年净值增长率    | %     |
| c_ret_2y          | DECIMAL(20,8) | 最近2年净值增长率    | %     |
| c_ret_3y          | DECIMAL(20,8) | 最近3年净值增长率    | %     |
| c_ret_4y          | DECIMAL(20,8) | 最近4年净值增长率    | %     |
| c_ret_5y          | DECIMAL(20,8) | 最近5年净值增长率    | %     |
| c_ret_ytd         | DECIMAL(20,8) | 今年以来净值增长率    | %     |
| c_ret_ly          | DECIMAL(20,8) | 去年净值增长率      | %     |
| c_ret_2ya         | DECIMAL(20,8) | 前年净值增长率      | %     |
| c_ret_3ya         | DECIMAL(20,8) | 往前第三年净值增长率   | %     |
| c_ret_4ya         | DECIMAL(20,8) | 往前第四年净值增长率   | %     |
| c_ret_5ya         | DECIMAL(20,8) | 往前第五年净值增长率   | %     |
| c_log_ret_adj     | DECIMAL(20,8) | 当日复权净值对数收益率  | -     |
| c_purchase_status | VARCHAR(20)   | 申购状态         | 见枚举值  |
| c_redeem_status   | VARCHAR(20)   | 赎回状态         | 见枚举值  |
| c_ret_1d          | DECIMAL(20,8) | 当日净值增长率      | %     |
| c_is_predict      | VARCHAR(2)    | 是否预测         | 1是/0否 |
| c_ret_1d_raw      | DECIMAL(20,8) | 当日净值增长率(不复权) | %     |
| c_is_trade        | VARCHAR(2)    | 是否交易日        | 1是/0否 |

## 枚举值

### 是否预测 (c_is_predict) 和 是否交易日(c_is_trade)

| 代码 | 名称 |
|----|----|
| 0  | 否  |
| 1  | 是  |

## 使用示例

```sql
-- 查询某基金最近净值(仅交易日/非货基)
SELECT c_trade_date, c_nav, c_nav_acc, c_ret_1d
FROM tytdata.tb_fd_nav_daily
WHERE c_fd_code = '000001'
  and c_trade_date between '2024-06-30' and '2024-12-31'
  and c_is_trade = '1';

-- 查询基金区间收益率
SELECT c_fd_code, c_ret_1m, c_ret_3m, c_ret_6m, c_ret_1y, c_ret_ytd
FROM tytdata.tb_fd_nav_daily
WHERE c_fd_code = '000001'
  and c_trade_date between '2024-06-30' and '2024-12-31'
ORDER BY c_ret_ytd DESC;
```
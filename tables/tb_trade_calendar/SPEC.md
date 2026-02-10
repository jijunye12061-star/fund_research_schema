# tb_trade_calendar - 交易日历表

## 基本信息

- **主键**: c_date
- **表类型**: Oracle视图映射
- **数据实效**: 实时同步

## 数据来源

- **Oracle表**: TYTFUND.CUST_CALENDER
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: WHERE EISDEL = '0'

## 字段清单

| 字段名               | 类型      | 注释     | 说明        |
|-------------------|---------|--------|-----------|
| c_date            | DATE    | 自然日期   | 主键        |
| c_is_trade        | TINYINT | 是否交易日  | 1是/0否     |
| c_prev_trade_date | DATE    | 前1个交易日 | 自然日前1个交易日 |
| c_max_trade_date  | DATE    | 最新交易日  | 当日前最新的交易日 |

## 枚举值

### 标识字段取值

| 字段值 | 含义 |
|-----|----|
| 1   | 是  |
| 0   | 否  |

## 使用示例

```sql
-- 获取2024年所有交易日
SELECT c_date as c_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_date BETWEEN '2024-01-01' AND '2024-12-31'
  AND c_is_trade = 1
ORDER BY c_trade_date;

-- 获取某天的最新交易日
SELECT c_max_trade_date as c_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_date = '2024-12-31';

-- 获取某交易日的前一交易日
SELECT c_prev_trade_date as c_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_date = '2024-12-31';

```

## 注意事项

- `c_date` 为全量自然日，使用时需过滤 `c_is_trade = 1` 获取交易日
- 交易日区间查询范式：
```sql
WHERE c_date BETWEEN :start_date AND :end_date AND c_is_trade = 1
```
# tb_trade_calendar - 交易日历表

## 基本信息

- **主键**: c_trade_date
- **表类型**: Oracle视图映射
- **数据实效**: 实时同步
- **数据范围**: 1991-01-01至今

## 数据来源

- **Oracle表**: TYTFUND.QT_TRADE_CALENDAR
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: WHERE C_ISDEL = '0'

## 字段清单

| 字段名                  | 类型      | 注释      | 说明           |
|----------------------|---------|---------|--------------|
| c_trade_date         | DATE    | 交易日期    | 主键           |
| c_is_trade_day       | TINYINT | 是否交易日   | 1是/0否        |
| c_is_week_end        | TINYINT | 是否周末交易日 | 1是/0否        |
| c_is_month_end       | TINYINT | 是否月末交易日 | 1是/0否        |
| c_is_quarter_end     | TINYINT | 是否季末交易日 | 1是/0否        |
| c_is_year_end        | TINYINT | 是否年末交易日 | 1是/0否        |
| c_pre_1d             | DATE    | 前1个交易日  | 自然日前1个交易日    |
| c_pre_1w             | DATE    | 前1周交易日  | 约5个交易日前      |
| c_pre_1m             | DATE    | 前1月交易日  | 约21个交易日前     |
| c_pre_3m             | DATE    | 前3月交易日  | 约63个交易日前     |
| c_pre_6m             | DATE    | 前6月交易日  | 约126个交易日前    |
| c_pre_1y             | DATE    | 前1年交易日  | 约252个交易日前    |
| c_pre_2y             | DATE    | 前2年交易日  | 约504个交易日前    |
| c_pre_3y             | DATE    | 前3年交易日  | 约756个交易日前    |
| c_pre_5y             | DATE    | 前5年交易日  | 约1260个交易日前   |
| c_is_fix_quarter_end | TINYINT | 是否固定季末  | 3/6/9/12月末为1 |

## 枚举值

### 标识字段取值

| 字段值 | 含义 |
|-----|----|
| 1   | 是  |
| 0   | 否  |

## 使用示例

```sql
-- 获取2024年所有交易日
SELECT c_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_trade_date BETWEEN '2024-01-01' AND '2024-12-31'
  AND c_is_trade_day = 1
ORDER BY c_trade_date;

-- 获取2024年所有月末交易日
SELECT c_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_trade_date BETWEEN '2024-01-01' AND '2024-12-31'
  AND c_is_month_end = 1;

-- 获取某日期的前1月/前3月/前1年交易日
SELECT c_trade_date, c_pre_1m, c_pre_3m, c_pre_1y
FROM tytdata.tb_trade_calendar
WHERE c_trade_date = '2024-11-27';

-- 计算两个日期间的交易日天数
SELECT COUNT(*) as trade_days
FROM tytdata.tb_trade_calendar
WHERE c_trade_date BETWEEN '2024-01-01' AND '2024-11-27'
  AND c_is_trade_day = 1;
```

## 注意事项

1. **PRE_XX字段规则**: 基于交易日倒推，非自然日倒推
2. **固定季末**: c_is_fix_quarter_end标识3/6/9/12月末（与自然季度对应）
3. **数据范围**: 包含所有自然日（is_trade_day=0的也在表中）
4. **高频使用**: 建议缓存到内存或使用Doris查询
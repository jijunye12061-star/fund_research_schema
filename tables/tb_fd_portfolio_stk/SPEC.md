# tb_fd_portfolio_stk - 基金股票投资组合表

## 基本信息

- **主键**: (c_fd_code, c_report_date, c_stk_code, c_style)
- **表类型**: Oracle视图映射
- **数据实效**: 实时同步

## 数据来源
- **Oracle表**: TYTFUND.FUND_IV_STOCKINVESTO
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: WHERE EISDEL = '0'

## 字段清单

| 字段名           | 类型            | 注释     | 说明      |
|---------------|---------------|--------|---------|
| c_fd_code     | VARCHAR(20)   | 基金代码   | 六位代码    |
| c_report_date | DATE          | 报告日期   | 季报截止日   |
| c_stk_code    | VARCHAR(20)   | 股票代码   | 六位代码    |
| c_style       | VARCHAR(10)   | 报表类别   | 见枚举值    |
| c_invest_type | VARCHAR(10)   | 投资类型   | 见枚举值    |
| c_notice_date | DATE          | 公告日期   | 披露日期    |
| c_inner_code  | VARCHAR(20)   | 股票内码   | 股票内码    |
| c_hold_value  | DECIMAL(18,4) | 持仓市值   | 单位：元    |
| c_hold_share  | DECIMAL(18,0) | 持仓股数   | 单位：股    |
| c_nav_ratio   | DECIMAL(18,4) | 占净值比例  | 单位：%    |
| c_is_stat     | TINYINT       | 是否合并统计 | -1主/0分级 |

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

### 投资类型 (c_invest_type)

| 代码 | 名称   | 说明             |
|----|------|----------------|
| 1  | 积极投资 | 指数基金非指数成分股的投资  |
| 2  | 指数投资 | 指数型基金的被动投资     |
| 3  | 综合投资 | 主动权益基金的投资类型均为3 |

## 使用示例

```sql
-- 查询某基金最新季报股票持仓
SELECT c_stk_code, c_hold_value, c_nav_ratio
FROM tytdata.tb_fd_portfolio_stk
WHERE c_fd_code = '000001'
  AND c_report_date = '2024-06-30'
  AND c_style = '02'
ORDER BY c_nav_ratio DESC;

-- 查询某股票被持有情况
SELECT c_fd_code, c_hold_value, c_hold_share
FROM tytdata.tb_fd_portfolio_stk
WHERE c_stk_code = '600000'
  AND c_report_date = '2024-06-30'
  AND c_style = '02'
ORDER BY c_hold_value DESC;

-- 统计基金前十大重仓股
SELECT c_stk_code, c_hold_value, c_nav_ratio
FROM tytdata.tb_fd_portfolio_stk
WHERE c_fd_code = '000001'
  AND c_report_date = '2024-06-30'
  AND c_style = '02'
ORDER BY c_nav_ratio DESC
LIMIT 10;
```
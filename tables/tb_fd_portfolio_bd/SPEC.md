# tb_fd_portfolio_bd - 基金债券投资组合表

## 基本信息

- **主键**: (c_fd_code, c_report_date, c_bd_inner_code, c_style)
- **表类型**: Oracle视图映射
- **数据实效**: 实时同步

## 数据来源
- **Oracle表**: TYTFUND.FUND_IV_BONDINVESTO
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: WHERE EISDEL = '0'

## 字段清单

| 字段名             | 类型            | 注释     | 说明      |
|-----------------|---------------|--------|---------|
| c_fd_code       | VARCHAR(20)   | 基金代码   | 六位代码    |
| c_report_date   | DATE          | 报告日期   | 季报截止日   |
| c_bd_code       | VARCHAR(20)   | 债券代码   | 六位代码    |
| c_bd_type       | VARCHAR(10)   | 债券类型   | 见枚举值    |
| c_style         | VARCHAR(10)   | 报表类别   | 见枚举值    |
| c_notice_date   | DATE          | 公告日期   | 披露日期    |
| c_bd_inner_code | VARCHAR(20)   | 债券内码   | 债券内码    |
| c_bd_name       | VARCHAR(40)   | 债券名称   | -       |
| c_hold_num      | DECIMAL(18,0) | 持仓数量   | 单位：张    |
| c_hold_value    | DECIMAL(18,4) | 持仓市值   | 单位：元    |
| c_nav_ratio     | DECIMAL(18,4) | 占净值比例  | 单位：%    |
| c_is_stat       | TINYINT       | 是否参与统计 | -1主/0分级 |

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

### 债券类型 (c_bd_type)

| 代码 | 名称     |
|----|--------|
| 1  | 债券     |
| 2  | 转股期可转债 |

## 使用示例

```sql
-- 查询某基金最新季报债券持仓
SELECT c_bd_code, c_bd_name, c_hold_value, c_nav_ratio
FROM tytdata.tb_fd_portfolio_bd
WHERE c_fd_code = '000001'
  AND c_report_date = '2024-06-30'
  AND c_style = '02'
ORDER BY c_nav_ratio DESC
```

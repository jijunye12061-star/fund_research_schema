# Oracle → Doris 视图映射指南

> 从 TYTFUND 原始表生成 Doris 视图的标准流程。

## 视图 SQL 模板

```sql
CREATE VIEW tytdata.
            {doris_view_name} (
            {doris_col_1} COMMENT '{注释}',
            {doris_col_2} COMMENT '{注释}',
            ...
            ) COMMENT '{表中文名}'
AS
SELECT
    {ORACLE_COL_1} as {doris_col_1}, {ORACLE_COL_2} as {doris_col_2}, ...
    FROM TYTFUND.{ORACLE_TABLE_NAME}
WHERE EISDEL = 0;
```
备注：有些表可能`EISDEL`字段为Null，需注意

## 完整示例

```sql
CREATE VIEW tytdata.tb_fd_portfolio_bd
            (
             c_fd_code COMMENT '基金代码',
             c_report_date COMMENT '报告日期',
             c_bd_code COMMENT '债券代码',
             c_bd_type COMMENT '债券类型',
             c_style COMMENT '报表类别',
             c_notice_date COMMENT '公告日期',
             c_inner_code COMMENT '债券内码',
             c_bd_name COMMENT '债券名称',
             c_hold_num COMMENT '持仓数量',
             c_hold_value COMMENT '持仓市值',
             c_nav_ratio COMMENT '占净值比例',
             c_is_stat COMMENT '是否参与统计'
                ) COMMENT '基金债券投资组合表'
AS
SELECT FUNDCODE   as c_fd_code,
       ENDDATE    as c_report_date,
       BONDCODE   as c_bd_code,
       BONDTYPE   as c_bd_type,
       STYLE      as c_style,
       NOTICEDATE as c_notice_date,
       INNERCODE  as c_inner_code,
       BONDNAME   as c_bd_name,
       BONDNUM    as c_hold_num,
       BONDVALUE  as c_hold_value,
       PCTNV      as c_nav_ratio,
       ISSTAT     as c_is_stat
FROM TYTFUND.FUND_IV_BONDINVESTO
WHERE EISDEL = '0';
```

## 映射文档模板（SPEC.md 中的数据来源部分）

| Oracle字段 | Doris字段       | 类型          | 注释   | 默认值处理       |
|----------|---------------|-------------|------|-------------|
| FUNDCODE | c_fd_code     | VARCHAR(20) | 基金代码 | -           |
| ENDDATE  | c_report_date | DATE        | 报告日期 | -           |
| ...      | ...           | ...         | ...  | NVL(..., 0) |

## 生成视图需要提供的信息

1. **原表名**（如 `TYTFUND.FUND_IV_BONDINVESTO`）
2. **视图名**（如 `tytdata.tb_fd_portfolio_bd`）
3. **字段映射**（Oracle字段 → Doris字段）
4. **过滤条件**（通常 `WHERE EISDEL = '0'`）
5. **枚举值说明**（如有）

## 注意事项

- 视图不能加索引，索引只能建在底层物理表上
- 视图查询性能不如物化表，频繁查询的大表建议物化
- Oracle 字段名使用大写（`EISDEL` 不是 `eisdel`）
- 源表 schema 是 `TYTFUND`，视图 schema 是 `tytdata`
- PyCharm 的 MySQL/Oracle 方言不认识 Doris 的 VIEW COMMENT 语法，忽略警告即可
- 债券表用内码（`c_inner_code`）做主键更合理（同一债券跨市场代码不同）

## 何时用视图 vs 物化表

| 条件               | 建议 |
|------------------|----|
| 简单字段映射           | 视图 |
| 需要多表 JOIN / 数据清洗 | 物化 |
| 数据量小、查询不频繁       | 视图 |
| 频繁关联查询 / 性能要求    | 物化 |
| 需要 Doris 索引      | 物化 |

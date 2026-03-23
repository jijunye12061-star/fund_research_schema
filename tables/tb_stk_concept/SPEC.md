# tb_stk_concept - A股股票概念归属表(日频)

## 基本信息

- **主键**: (c_trade_date, c_stk_code, c_concept_code)
- **表类型**: 计算型
- **更新频率**: 日度增量
- **数据范围**: 全A股(含CDR), 2015-01-01至今
- **分区方式**: 按月动态分区(含历史分区), 每分区1桶
- **依赖表**: tb_stk_basic_info(股票列表), tb_trade_calendar(交易日历)

## 数据来源

- **Oracle表**: TYTFUND.CDSY_KP_PUBLISHHISSTOCK (概念调入I/调出D事件)
- **计算逻辑**: 对每个(股票, 概念)取截至该交易日最近一条事件, 仅保留最近事件为I的
- **与tb_stk_industry的区别**: 一股多概念(多对多), 且需处理D(移出)事件

## 字段清单

| 字段名            | 类型          | 注释   | 说明                 |
|----------------|-------------|------|--------------------|
| c_trade_date   | DATE        | 交易日期 | 仅交易日               |
| c_stk_code     | VARCHAR(20) | 证券代码 | 六位代码               |
| c_concept_code | VARCHAR(12) | 概念代码 | PUBLISHCODE, 007前缀 |
| c_updatetime   | DATETIME(6) | 更新时间 | 系统自动生成             |

## 概念名称查询

通过 `tb_dict_params` 字典表关联:

```sql
-- c_param_type = '概念板块'
-- c_param_code = 概念代码
-- c_param_name = 概念名称
-- c_parent_code = '007'
-- c_remark = 概念简介(用于RAG检索)
```

字典来源: `NEWSADMIN.CDSY_KP_PUBLISHINDEX`, 由 `insert.py` 中 `sync_dict()` 同步。

## 使用示例

```sql
-- 查询某股票当前所属概念
SELECT a.c_stk_code, d.c_param_name AS concept_name
FROM tytdata.tb_stk_concept a
         JOIN tytdata.tb_dict_params d
              ON d.c_param_type = '概念板块'
                  AND d.c_param_code = a.c_concept_code
WHERE a.c_stk_code = '002050'
  AND a.c_trade_date = '2026-03-23';

-- 某概念的成分股列表
SELECT a.c_stk_code, b.c_stk_name
FROM tytdata.tb_stk_concept a
         JOIN tytdata.tb_stk_basic_info b ON a.c_stk_code = b.c_stk_code
WHERE a.c_concept_code = '007001'
  AND a.c_trade_date = '2026-03-23';

-- 基金持仓的概念分布
SELECT d.c_param_name               AS concept_name,
       COUNT(DISTINCT a.c_stk_code) AS stk_count,
       SUM(a.c_hold_value)          AS total_mv
FROM tytdata.tb_fd_portfolio_stk a
         JOIN tytdata.tb_stk_concept b
              ON a.c_stk_code = b.c_stk_code
                  AND a.c_report_date = b.c_trade_date
         JOIN tytdata.tb_dict_params d
              ON d.c_param_type = '概念板块'
                  AND d.c_param_code = b.c_concept_code
WHERE a.c_fd_code = '000001'
  AND a.c_report_date = '2025-06-30'
  AND a.c_style = '02'
GROUP BY d.c_param_name
ORDER BY total_mv DESC;

-- RAG场景: 模糊匹配概念(全量拉取供LLM选择)
SELECT c_param_code, c_param_name, c_remark
FROM tytdata.tb_dict_params
WHERE c_param_type = '概念板块';
```
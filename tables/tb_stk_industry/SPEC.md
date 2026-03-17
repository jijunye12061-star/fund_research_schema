# tb_stk_industry - A股股票行业归属表(日频)

## 基本信息

- **主键**: (c_trade_date, c_stk_code)
- **更新频率**: 日度增量
- **数据范围**: 全A股(含CDR), 2015-01-01至今
- **分区方式**: 按月动态分区(含历史分区), 每分区1桶
- **依赖表**: tb_stk_basic_info(股票列表), tb_trade_calendar(交易日历)

## 数据来源

- **Oracle表**: TYTFUND.CDSY_KP_PUBLISHHISSTOCK (行业调入I/调出D事件)
- **计算逻辑**: 对每只股票取截至该交易日最近一次I事件的行业代码
- **行业代码**: 存储三级代码(12位), 截断即可获取高级别:
    - `LEFT(code, 6)` → 一级行业
    - `LEFT(code, 9)` → 二级行业
    - 完整12位 → 三级行业

## 字段清单

| 字段名          | 类型          | 注释         | 说明                      |
|--------------|-------------|------------|-------------------------|
| c_trade_date | DATE        | 交易日期       | 仅交易日                    |
| c_stk_code   | VARCHAR(20) | 证券代码       | 六位代码                    |
| c_citic_code | VARCHAR(12) | 中信行业代码(三级) | PUBLISHCODE前缀025        |
| c_sw_code    | VARCHAR(12) | 申万行业代码(三级) | 2021-07-30前用011, 之后用029 |
| c_updatetime | DATETIME(6) | 更新时间       | 系统自动生成                  |

## 申万行业新旧体系

| 时段            | PUBLISHCODE前缀 | 说明       |
|---------------|---------------|----------|
| < 2021-07-30  | 011           | 申万旧版行业分类 |
| >= 2021-07-30 | 029           | 申万新版行业分类 |

> 注意: c_sw_code在切换日前后的前缀不同, 关联字典表时需注意

## 行业名称查询

通过 `tb_dict_params` 字典表关联获取行业名称:

```sql
-- c_param_type = '中信行业分类' / '申万行业分类'
-- c_param_code = 行业代码
-- c_param_name = 行业名称
-- c_parent_code = 上级行业代码
```

## 使用示例

```sql
-- 查询某股票某日所属中信三级行业
SELECT c_stk_code, c_citic_code
FROM tytdata.tb_stk_industry
WHERE c_stk_code = '000001'
  AND c_trade_date = '2025-12-31';

-- 关联字典表取中信一级行业名称
SELECT a.c_stk_code,
       LEFT(a.c_citic_code, 6) AS citic_l1_code,
       d.c_param_name          AS citic_l1_name
FROM tytdata.tb_stk_industry a
         LEFT JOIN tytdata.tb_dict_params d
                   ON d.c_param_type = '中信行业分类'
                       AND d.c_param_code = LEFT(a.c_citic_code, 6)
WHERE a.c_trade_date = '2025-12-31';

-- 各中信一级行业股票数量
SELECT LEFT(c_citic_code, 6) AS citic_l1,
       COUNT(*)              AS cnt
FROM tytdata.tb_stk_industry
WHERE c_trade_date = '2025-12-31'
GROUP BY LEFT(c_citic_code, 6)
ORDER BY cnt DESC;

-- 某股票行业变更历史
SELECT c_trade_date, c_citic_code
FROM (SELECT c_trade_date,
             c_citic_code,
             LAG(c_citic_code, 1, NULL) OVER (ORDER BY c_trade_date) AS prev
      FROM tytdata.tb_stk_industry
      WHERE c_stk_code = '000001') t
WHERE c_citic_code != prev
   OR prev IS NULL;

-- 基金持仓的行业分布
SELECT LEFT(b.c_citic_code, 6) AS industry,
       d.c_param_name          AS industry_name,
       SUM(a.c_hold_value)     AS total_mv
FROM tytdata.tb_fd_portfolio_stk a
         JOIN tytdata.tb_stk_industry b
              ON a.c_stk_code = b.c_stk_code AND a.c_report_date = b.c_trade_date
         LEFT JOIN tytdata.tb_dict_params d
                   ON d.c_param_type = '中信行业分类' AND d.c_param_code = LEFT(b.c_citic_code, 6)
WHERE a.c_fd_code = '000001'
  AND a.c_report_date = '2025-06-30'
AND a.c_style = '02'
GROUP BY LEFT(b.c_citic_code, 6), d.c_param_name;
```
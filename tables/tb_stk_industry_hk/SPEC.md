# tb_stk_industry_hk - 港股股票行业归属表(静态快照)

## 基本信息

- **主键**: c_stk_code
- **表类型**: calc表(Python计算写入)
- **更新频率**: 低频全量覆盖, `run(calc_date)` 传入日期
- **数据范围**: 全部港股(H股、非H股、红筹股), 截至calc_date已上市未退市
- **分区方式**: 无分区, 1桶

## 数据来源

- **Oracle表**: TYTFUND.CDSY_KP_PUBLISHSTOCK (行业现状表)
- **计算逻辑**: 从现状表取各分类口径最细粒度代码, 按股票代码合并为宽表
- **设计说明**: 港股历史行业变动数据不完整(407/408无历史, 402/403仅到2018), 故采用静态快照而非日频展开

## 行业分类口径

| 字段           | 前缀  | 字典param_type | 说明          |
|--------------|-----|--------------|-------------|
| c_sw_code    | 029 | 申万行业分类       | 申万体系, 与A股统一 |
| c_citic_code | 407 | 港股中信行业分类     | 中信对港股的覆盖    |
| c_hkex_code  | 403 | 港交所行业分类      | 港交所本地分类     |
| c_gics_code  | 402 | GICS行业分类     | 全球标准, 四级15位 |

代码层级: `LEFT(code, 6)` → 一级, `LEFT(code, 9)` → 二级, `LEFT(code, 12)` → 三级, GICS额外有 `LEFT(code, 15)` → 四级

## 字段清单

| 字段名          | 类型          | 注释           | 说明             |
|--------------|-------------|--------------|----------------|
| c_stk_code   | VARCHAR(20) | 证券代码         | 港股5位代码, 如00700 |
| c_sw_code    | VARCHAR(12) | 申万行业代码(三级)   | 029前缀          |
| c_citic_code | VARCHAR(12) | 中信行业代码(三级)   | 407前缀          |
| c_hkex_code  | VARCHAR(12) | 港交所行业代码(三级)  | 403前缀          |
| c_gics_code  | VARCHAR(15) | GICS行业代码(四级) | 402前缀, 15位     |
| c_updatetime | DATETIME(6) | 更新时间         | 系统自动生成         |

## 覆盖率参考(2025年数据)

| 口径   | 覆盖港股数 | 备注         |
|------|-------|------------|
| 029  | ~828  | 主要覆盖沪深港通标的 |
| 407  | ~2578 | 覆盖较全       |
| 403  | ~2866 | 最全, 含部分已退市 |
| 402  | ~2776 | 覆盖较全       |
| 港股总数 | ~2718 | 正常上市       |

## 与A股行业表的差异

| 对比项  | tb_stk_industry (A股)    | tb_stk_industry_hk (港股) |
|------|-------------------------|-------------------------|
| 粒度   | 日频(交易日×股票)              | 静态快照(每只股票一行)            |
| 分区   | 按月动态分区                  | 无分区                     |
| 行业列  | c_citic_code, c_sw_code | 4列(申万/中信/港交所/GICS)      |
| 历史变动 | 完整历史                    | 仅最新, 无历史                |

## 使用示例

```sql
-- 查询腾讯的行业归属
SELECT c_stk_code, c_sw_code, c_citic_code, c_hkex_code, c_gics_code
FROM tytdata.tb_stk_industry_hk
WHERE c_stk_code = '00700';

-- 关联字典表取申万一级行业名称
SELECT a.c_stk_code,
       LEFT(a.c_sw_code, 6) AS sw_l1_code,
       d.c_param_name       AS sw_l1_name
FROM tytdata.tb_stk_industry_hk a
         LEFT JOIN tytdata.tb_dict_params d
                   ON d.c_param_type = '申万行业分类'
                       AND d.c_param_code = LEFT(a.c_sw_code, 6)
WHERE a.c_sw_code IS NOT NULL;

-- 各中信一级行业港股数量
SELECT LEFT(c_citic_code, 6) AS citic_l1,
       d.c_param_name        AS citic_l1_name,
       COUNT(*)              AS cnt
FROM tytdata.tb_stk_industry_hk a
         LEFT JOIN tytdata.tb_dict_params d
                   ON d.c_param_type = '港股中信行业分类'
                       AND d.c_param_code = LEFT(a.c_citic_code, 6)
WHERE a.c_citic_code IS NOT NULL
GROUP BY LEFT(c_citic_code, 6), d.c_param_name
ORDER BY cnt DESC;

-- 基金港股持仓的行业分布(用中信)
SELECT LEFT(b.c_citic_code, 6) AS industry,
       d.c_param_name          AS industry_name,
       SUM(a.c_hold_value)     AS total_mv
FROM tytdata.tb_fd_portfolio_stk a
         JOIN tytdata.tb_stk_industry_hk b ON a.c_stk_code = b.c_stk_code
         LEFT JOIN tytdata.tb_dict_params d
                   ON d.c_param_type = '港股中信行业分类'
                       AND d.c_param_code = LEFT(b.c_citic_code, 6)
WHERE a.c_fd_code = '000001'
  AND a.c_report_date = '2025-06-30'
  AND a.c_style = '02'
GROUP BY LEFT(b.c_citic_code, 6), d.c_param_name;
```
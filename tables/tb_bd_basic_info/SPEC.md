# tb_bd_basic_info - 债券基础信息表

## 基本信息

- **主键**: c_bd_inner_code（内码跨市场唯一）
- **表类型**: Oracle 视图映射
- **数据实效**: 实时同步
- **数据量**: ~59 万条（全量债券，含已退市）

## 数据来源

- **Oracle 表**: `TYTFUND.BOND_BA_INFO`
- **映射方式**: `CREATE VIEW` 直接映射
- **过滤条件**: `WHERE EISDEL = '0'`

## 字段清单

| 字段名           | Oracle 字段              | 类型           | 注释              | 说明                      |
|----------------|------------------------|--------------|-----------------|-------------------------|
| c_bd_code      | BONDCODE               | VARCHAR(20)  | 债券代码（6位）       | 同一债券跨市场代码不同             |
| c_bd_inner_code | SECURITYVARIETYCODE   | VARCHAR(20)  | 债券内码           | 全局唯一，推荐做 JOIN 关联键       |
| c_bd_name      | SNAME                  | VARCHAR(40)  | 债券简称           | -                       |
| c_bd_full_name | FNAME                  | VARCHAR(200) | 债券全称           | -                       |
| c_bd_type      | BONDTYPE               | VARCHAR(40)  | 债券类型（文本）       | 共44种，见枚举值；注意与 tb_fd_portfolio_bd.c_bd_type 含义不同 |
| c_bd_type_code | BONDTYPECODE           | VARCHAR(20)  | 债券类型代码         | -                       |
| c_stk_code     | SWAPSCODE              | VARCHAR(20)  | 正股代码           | 仅转债类有值，约 1,629 条        |
| c_issue_date   | ISSUEDATE              | DATE         | 发行日             | -                       |
| c_list_date    | LISTDATE               | DATE         | 上市日             | -                       |
| c_delist_date  | DELISTDATE             | DATE         | 退市日             | NULL = 存续中（约 10 万条）；通常比到期日早 1-3 个工作日 |
| c_maturity_date | MRTYDATE              | DATE         | 到期日             | NULL = 永续债（约 168 条）  |
| c_issue_vol    | ISSUEVOL               | DECIMAL(20,4) | 发行规模（亿元）      | -                       |
| c_par_value    | PARVALUE               | DECIMAL(10,4) | 面值              | 通常为 100                |
| c_coupon_rate  | COUPONRATE             | DECIMAL(10,4) | 票面利率（%）        | -                       |
| c_credit_rating | CREDITRATING          | VARCHAR(20)  | 信用评级           | 如 AAA、AA+、AA 等         |
| c_exchange     | TEXCH                  | VARCHAR(20)  | 交易所             | 见枚举值                   |

## 枚举值

### 债券类型 (c_bd_type) — 有正股代码的 3 种类型

| 取值            | BONDTYPECODE | 说明              |
|---------------|--------------|-----------------|
| 可转换债券         | 060005008    | 标准 A 股上市转债       |
| 可交换债券         | 060005010    | 正股来自大股东持仓，不摊薄  |
| 可分离交易可转债      | 060005009    | 权证已分离，当前存量极少   |

> 注意：本表 `c_bd_type` 是文本（债券品种名称），`tb_fd_portfolio_bd.c_bd_type` 是数字编码（'1'债券/'2'转股期CB），两者含义不同，不能直接比较。
>
> `c_coupon_rate` 对转债类通常为 NULL（转债采用票息步进结构，原始票面利率字段不适用）。

### 交易所 (c_exchange) — 主要市场

| 取值     | 说明          | 数量   |
|--------|-------------|------|
| CNIBEX | 银行间市场       | ~45万 |
| CNSESH | 上海证券交易所     | ~8.5万 |
| CNSESZ | 深圳证券交易所     | ~3.8万 |
| CNCONT | 柜台市场        | ~1万  |
| CNSEBJ | 北京证券交易所     | ~680 |
| ZJGQEX 等 | 各地区股权交易中心 | 少量  |

## 使用示例

```sql
-- 查询全部可转换债券基础信息
SELECT c_bd_code, c_bd_name, c_stk_code, c_list_date, c_delist_date, c_issue_vol
FROM tytdata.tb_bd_basic_info
WHERE c_bd_type = '可转换债券'
ORDER BY c_list_date DESC;

-- 通过正股代码反查转债
SELECT c_bd_code, c_bd_name, c_issue_vol, c_maturity_date
FROM tytdata.tb_bd_basic_info
WHERE c_stk_code = '600519'
  AND c_bd_type = '可转换债券';

-- 识别 tb_fd_portfolio_bd 中 c_bd_type='1' 里混入的可转债
SELECT p.c_fd_code, p.c_bd_code, b.c_bd_type
FROM tytdata.tb_fd_portfolio_bd p
JOIN tytdata.tb_bd_basic_info b ON p.c_bd_code = b.c_bd_code
WHERE p.c_bd_type = '1'
  AND b.c_bd_type = '可转换债券'
  AND p.c_report_date = '2025-03-31';
```

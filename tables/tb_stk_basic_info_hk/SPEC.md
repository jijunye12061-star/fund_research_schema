# tb_stk_basic_info_hk - 港股基本信息表

## 基本信息

- **主键**: c_stk_code
- **表类型**: Oracle视图映射
- **更新频率**: 每日
- **数据范围**: H股、非H股、红筹股

## 数据来源

- **Oracle表**: TYTFUND.CDSY_SECUCODE
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: SECURITYTYPECODE IN ('058001003001', '058001003002', '058001003003') AND USESTATE = 1 AND (EISDEL = 0 OR
  EISDEL IS NULL)

## 字段清单

| 字段名            | 类型           | 注释   | 说明           |
|----------------|--------------|------|--------------|
| c_stk_code     | VARCHAR(20)  | 证券代码 | 五位代码，如 00941 |
| c_inner_code   | VARCHAR(100) | 证券内码 | 关联其他数据表      |
| c_company_code | VARCHAR(100) | 公司代码 | 关联公司维度信息     |
| c_stk_name     | VARCHAR(200) | 证券简称 | -            |
| c_stk_type     | VARCHAR(50)  | 证券类型 | 见枚举值         |
| c_trade_market | VARCHAR(50)  | 交易市场 | 见枚举值         |
| c_list_date    | DATE         | 上市日期 | -            |
| c_delist_date  | DATE         | 退市日期 | 正常上市时为NULL   |
| c_list_status  | VARCHAR(20)  | 上市状态 | 见枚举值         |
| c_updatetime   | DATETIME(6)  | 更新时间 | 自动更新         |

## 枚举值

### 证券类型 (c_stk_type)

| 值   | 代码           | 说明            |
|-----|--------------|---------------|
| H股  | 058001003001 | 大陆注册、港交所上市    |
| 非H股 | 058001003002 | 香港或海外注册、港交所上市 |
| 红筹股 | 058001003003 | 境外注册、实际业务在大陆  |

### 交易市场 (c_trade_market)

| 值        | 说明    |
|----------|-------|
| 香港交易所主板  | 主板上市  |
| 香港交易所创业板 | 创业板上市 |

### 上市状态 (c_list_status)

| 值      | 说明      |
|--------|---------|
| 正常上市   | 正常交易中   |
| 终止上市   | 已退市     |
| 未上市    | 尚未上市    |

## 使用示例

```sql
-- 查询当前正常上市的港股
SELECT c_stk_code, c_stk_name, c_stk_type, c_trade_market
FROM tytdata.tb_stk_basic_info_hk
WHERE c_list_status = '正常上市';

-- 按证券类型统计
SELECT c_stk_type, COUNT(*) AS cnt
FROM tytdata.tb_stk_basic_info_hk
WHERE c_list_status = '正常上市'
GROUP BY c_stk_type
ORDER BY cnt DESC;

-- 筛选主板H股
SELECT c_stk_code, c_stk_name
FROM tytdata.tb_stk_basic_info_hk
WHERE c_stk_type = 'H股'
  AND c_trade_market = '香港交易所主板'
  AND c_list_status = '正常上市';
```
# tb_stk_basic_info - 股票基本信息表

## 基本信息

- **主键**: c_stk_code
- **表类型**: Oracle视图映射
- **更新频率**: 每日
- **数据范围**: A股 + 中国存托凭证(CDR)

## 数据来源

- **Oracle表**: TYTFUND.CDSY_SECUCODE
- **映射方式**: CREATE VIEW直接映射
- **过滤条件**: SECURITYTYPECODE IN ('058001001', '058001008') AND USESTATE = '1' AND (EISDEL = '0' OR EISDEL IS NULL)

## 字段清单

| 字段名            | 类型           | 注释   | 说明                   |
|----------------|--------------|------|----------------------|
| c_stk_code     | VARCHAR(20)  | 证券代码 | 六位代码，如 000001、688001 |
| c_inner_code   | VARCHAR(100) | 证券内码 | 证券内码，用于关联其他数据表       |
| c_company_code | VARCHAR(100) | 公司代码 | 公司代码，关联公司维度信息        |
| c_stk_name     | VARCHAR(200) | 证券简称 | -                    |
| c_stk_type     | VARCHAR(50)  | 证券类型 | 见枚举值                 |
| c_trade_market | VARCHAR(50)  | 交易市场 | 见枚举值                 |
| c_list_date    | DATE         | 上市日期 | -                    |
| c_delist_date  | DATE         | 退市日期 | 正常上市时为NULL           |
| c_list_status  | VARCHAR(20)  | 上市状态 | 见枚举值                 |
| c_updatetime   | DATETIME(6)  | 更新时间 | 自动更新                 |

## 枚举值

### 证券类型 (c_stk_type)

| 值      | 说明        |
|--------|-----------|
| A股     | 人民币普通股票   |
| 中国存托凭证 | CDR，如九号公司 |

### 交易市场 (c_trade_market)

| 值        | 说明 |
|----------|----|
| 上交所主板    | -  |
| 上交所科创板   | -  |
| 深交所主板    | -  |
| 深交所创业板   | -  |
| 北京证券交易所  | -  |
| 深交所风险警示板 | -  |
| 上交所风险警示板 | -  |

### 上市状态 (c_list_status)

| 值      | 说明      |
|--------|---------|
| 正常上市   | 正常交易中   |
| 暂停上市   | 暂停交易    |
| 终止上市   | 已退市     |
| 恢复上市   | 暂停后恢复   |
| 未上市    | 尚未上市    |
| 资产重组弃用 | 重组后代码弃用 |

## 使用示例

```sql
-- 查询当前正常上市的A股
SELECT c_stk_code, c_stk_name, c_trade_market, c_list_date
FROM tytdata.tb_stk_basic_info
WHERE c_list_status = '正常上市'
  AND c_stk_type = 'A股';

-- 查询科创板股票列表
SELECT c_stk_code, c_stk_name, c_list_date
FROM tytdata.tb_stk_basic_info
WHERE c_trade_market = '上交所科创板'
  AND c_list_status = '正常上市'
ORDER BY c_list_date;

-- 通过公司代码关联公司维度信息
SELECT a.c_stk_code, a.c_stk_name, a.c_trade_market
FROM tytdata.tb_stk_basic_info a
WHERE a.c_company_code = '100001'
  AND a.c_list_status = '正常上市';
```
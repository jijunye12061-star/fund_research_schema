# tb_dict_params - 通用参数字典表

## 基本信息
- **主键**: (c_param_type, c_param_code)
- **更新频率**: 按需更新
- **数据范围**: 全市场参数

## 字段清单

| 字段名            | 类型           | 注释           | 说明           |
|----------------|--------------|--------------|--------------|
| c_param_type   | VARCHAR(50)  | 参数类型         | 如industry_sw |
| c_param_code   | VARCHAR(50)  | 参数代码         | 唯一标识         |
| c_param_name   | VARCHAR(200) | 参数名称         | -            |
| c_parent_code  | VARCHAR(50)  | 父级代码         | 一级为NULL      |
| c_remark       | VARCHAR(500) | 备注           | 补充说明         |
| c_updatetime   | DATETIME(6)  | 更新时间         | 自动更新         |

## 参数类型

| c_param_type   | 说明     | 层级  | 编码长度 |
|----------------|--------|-----|------|
| industry_sw    | 申万行业   | 3级  | 12位  |
| industry_citic | 中信行业   | 3级  | 6位   |
| industry_csrc  | 证监会行业  | 2级  | 4位   |
| industry_gics  | GICS行业 | 4级  | 8位   |
| report_style   | 报表类型   | 无   | 2位   |
| bond_type      | 债券类型   | 无   | 1位   |

## 使用示例
```sql
-- 获取参数名称
SELECT c_param_name 
FROM tb_dict_params 
WHERE c_param_type = 'report_style' 
  AND c_param_code = '01';

-- 获取一级行业
SELECT * FROM tb_dict_params 
WHERE c_param_type = 'industry_sw' 
  AND c_parent_code IS NULL;

-- 获取行业层级
SELECT c_param_code, c_param_name
FROM tb_dict_params
WHERE c_param_type = 'industry_sw'
  AND c_param_code IN ('801010000000', '801011000000', '801011010000');
```

## Python工具函数
```python
def get_param_name(param_type: str, param_code: str) -> str:
    """获取参数名称"""
    sql = f"""
    SELECT c_param_name FROM tb_dict_params 
    WHERE c_param_type = '{param_type}' 
      AND c_param_code = '{param_code}'
    """
    with DorisConnector() as doris:
        df = doris.query(sql)
    return df['c_param_name'].iloc[0] if len(df) > 0 else None

def get_industry_hierarchy(param_type: str, industry_code: str) -> dict:
    """获取行业三级层级"""
    # 根据不同体系解析
    if param_type == 'industry_sw':
        codes = [
            industry_code[:6].ljust(12, '0'),
            industry_code[:9].ljust(12, '0'),
            industry_code
        ]
    elif param_type == 'industry_citic':
        codes = [
            industry_code[:2].ljust(6, '0'),
            industry_code[:4].ljust(6, '0'),
            industry_code
        ]
    else:
        return {}
    
    sql = f"""
    SELECT c_param_code, c_param_name
    FROM tb_dict_params
    WHERE c_param_type = '{param_type}'
      AND c_param_code IN ('{"','".join(codes)}')
    ORDER BY LENGTH(c_param_code)
    """
    with DorisConnector() as doris:
        df = doris.query(sql)
    return dict(enumerate(df['c_param_name'], 1))
```
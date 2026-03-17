# tb_dict_params - 通用参数字典表

## 基本信息

- **主键**: (c_param_type, c_param_code)
- **更新频率**: 低频, 字典变动时手动触发
- **用途**: 存储项目中所有枚举/分类的代码→名称映射

## 字段清单

| 字段名           | 类型           | 注释    | 说明            |
|---------------|--------------|-------|---------------|
| c_param_type  | VARCHAR(50)  | 参数类型  | 命名空间, 区分不同字典  |
| c_param_code  | VARCHAR(50)  | 参数代码  | 类型内唯一         |
| c_param_name  | VARCHAR(200) | 参数名称  | 中文名称          |
| c_parent_code | VARCHAR(50)  | 父节点代码 | 树形结构用, 无层级则留空 |
| c_remark      | VARCHAR(500) | 备注    | 补充信息          |
| c_updatetime  | DATETIME(6)  | 更新时间  | 系统自动生成        |

## 已录入参数类型

### 行业分类 (insert_industry.py)

| c_param_type | 源表前缀 | 说明                    |
|--------------|------|-----------------------|
| 中信行业分类       | 025  | 中信行业分类2020, Barra模型使用 |
| 申万行业分类       | 029  | 2021-07-30起启用，含港美     |
| 申万行业分类(旧)    | 011  | 2021-07-30前使用         |
| 中证行业分类       | 033  | 2021版                 |
| 证监会行业分类      | 002  | 监管口径                  |
| GICS行业分类     | 003  | 全球标准                  |
| 港交所行业分类      | 403  | 港股本地分类                |
| 港股申万行业分类     | 408  | 申万对港股的覆盖              |
| 港股中信行业分类     | 407  | 中信对港股的覆盖              |

行业代码层级结构: 6位=一级, 9位=二级, 12位=三级, 通过 `c_parent_code` 关联上级。

### 规划中

| c_param_type | 说明       | 备注               |
|--------------|----------|------------------|
| 基金分类         | 组内基金分类体系 | 对应tb_fd_category |
| 债券类型         | 债券品种分类   | -                |
| 交易所          | SH/SZ/HK | -                |

## 使用示例

```sql
-- 查看中信一级行业列表
SELECT c_param_code, c_param_name
FROM tytdata.tb_dict_params
WHERE c_param_type = '中信行业分类'
  AND LENGTH(c_param_code) = 6
ORDER BY c_param_code;

-- 通过三级代码查完整层级名称
SELECT a.c_param_name AS l3_name,
       b.c_param_name AS l2_name,
       c.c_param_name AS l1_name
FROM tytdata.tb_dict_params a
         LEFT JOIN tytdata.tb_dict_params b
                   ON b.c_param_type = a.c_param_type AND b.c_param_code = a.c_parent_code
         LEFT JOIN tytdata.tb_dict_params c
                   ON c.c_param_type = a.c_param_type AND c.c_param_code = b.c_parent_code
WHERE a.c_param_type = '中信行业分类'
  AND a.c_param_code = '025001001001';

-- tb_stk_industry关联取行业名称
SELECT s.c_stk_code,
       d.c_param_name AS citic_l1_name
FROM tytdata.tb_stk_industry s
         JOIN tytdata.tb_dict_params d
              ON d.c_param_type = '中信行业分类'
                  AND d.c_param_code = LEFT(s.c_citic_code, 6)
WHERE s.c_trade_date = '2025-12-31';
```
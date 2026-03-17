# tb_dict_params - 通用参数字典表

## 基本信息

| 项目       | 说明                              |
|----------|---------------------------------|
| 表名       | tb_dict_params                  |
| Schema   | tytdata                         |
| 主键       | (c_param_type, c_param_code)    |
| 更新频率     | 按需更新                            |
| 数据范围     | 全市场行业分类体系                       |
| 数据来源     | Oracle TYTFUND.CDSY_KP_PUBLISHRELATION |

---

## 字段清单

| 字段名           | 类型           | 注释   | 说明                |
|---------------|--------------|------|-------------------|
| c_param_type  | VARCHAR(50)  | 参数类型 | 参数类别标识            |
| c_param_code  | VARCHAR(50)  | 参数代码 | 唯一标识              |
| c_param_name  | VARCHAR(200) | 参数名称 | 名称                |
| c_parent_code | VARCHAR(50)  | 父级代码 | 一级对应为c_param_type |
| c_remark      | VARCHAR(500) | 备注   | 补充说明              |
| c_updatetime  | DATETIME(6)  | 更新时间 | 自动更新              |

---

## 参数类型

| c_param_type | 说明        | 层级 | 源表前缀 |
|--------------|-----------|----|------|
| 002          | 证监会行业     | 2级 | 002% |
| 028          | 申万行业2021  | 3级 | 028% |
| 408          | 港股申万行业2021 | 3级 | 408% |
| 003          | GICS行业2021 | 3级 | 003% |
| 033          | 中证行业2021  | 3级 | 033% |
| 025          | 中信行业2020  | 3级 | 025% |
| 407          | 港股中信行业2020 | 3级 | 407% |
| 403          | 港交所分类     | 3级 | 403% |
| 004          | 东财分类      | 3级 | 004% |

---

## c_param_code 层级结构说明

以中信行业2020（c_param_type=025）为例：

```
025001        石油石化        (一级)
├── 025001001     石油开采II   (二级)
│   ├── 025001001001  石油开采III  (三级)
├── 025001002     石油化工     (二级)
│   ├── 025001002001  炼油        (三级)
│   ├── 025001002002  油品销售及仓储 (三级)
│   └── 025001002003  其他石化    (三级)
```

`c_parent_code` 为上一层级的 c_param_code

---

## 使用示例

> 其他业务表通常只存储参数代码（如行业代码），通过关联本表可将代码翻译为可读名称。

```sql
-- 场景1：将持仓表中的行业代码翻译为行业名称（申万2021）
SELECT
    t.c_stock_code,
    t.c_sw_industry_code,
    p.c_param_name AS c_sw_industry_name   -- 通过代码查名称
FROM your_table t
LEFT JOIN tytdata.tb_dict_params p
    ON p.c_param_type = '028'
    AND p.c_param_code = t.c_sw_industry_code;

-- 场景2：已知行业代码，直接查对应名称
SELECT c_param_name
FROM tytdata.tb_dict_params
WHERE c_param_type = '025'          -- 中信行业2020
  AND c_param_code = '025001001';   -- 查询该代码的名称 → 石油开采II

-- 场景3：获取某体系所有一级分类的代码与名称（用于下拉菜单等）
SELECT c_param_code, c_param_name
FROM tytdata.tb_dict_params
WHERE c_param_type = '028'
  AND LENGTH(c_param_code) = 6;    -- 一级行业编码长度

-- 场景4：获取某一级行业下所有二级分类的代码与名称
SELECT c_param_code, c_param_name
FROM tytdata.tb_dict_params
WHERE c_param_type = '025'
  AND c_parent_code = '025001';    -- 石油石化 下属所有二级行业
```

---

## Python 工具函数

```python
def get_param_name(param_type: str, param_code: str) -> str | None:
    """
    根据参数代码查询对应名称。
    适用于其他表中存有行业代码，需翻译为可读名称的场景。

    示例：
        get_param_name('025', '025001001')  →  '石油开采II'
    """
    sql = f"""
    SELECT c_param_name FROM tytdata.tb_dict_params
    WHERE c_param_type = '{param_type}'
      AND c_param_code = '{param_code}'
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql)
    return df['c_param_name'].iloc[0] if len(df) > 0 else None


def translate_code_column(
    df: pd.DataFrame,
    code_col: str,
    param_type: str,
    name_col: str = None
) -> pd.DataFrame:
    """
    将 DataFrame 中某列的参数代码批量翻译为名称，新增一列返回。
    适用于持仓、个股等业务表中批量翻译行业代码的场景。

    参数：
        df         - 包含参数代码列的 DataFrame
        code_col   - 参数代码所在列名
        param_type - 参数类型，如 '028'（申万2021）
        name_col   - 新增名称列的列名，默认为 code_col + '_name'

    示例：
        df = translate_code_column(df, 'c_sw_code', '028')
        # 新增列 c_sw_code_name，内容为对应的申万行业名称
    """
    if name_col is None:
        name_col = code_col + '_name'

    sql = f"""
    SELECT c_param_code, c_param_name
    FROM tytdata.tb_dict_params
    WHERE c_param_type = '{param_type}'
    """
    with DorisConnector(ENV) as doris:
        mapping_df = doris.query(sql)

    code_to_name = dict(zip(mapping_df['c_param_code'], mapping_df['c_param_name']))
    df[name_col] = df[code_col].map(code_to_name)
    return df


def get_industry_hierarchy(param_type: str, leaf_code: str) -> dict:
    """
    根据末级行业代码，向上回溯完整的层级路径，返回各级名称。
    适用于其他表中只记录了末级代码，需要还原完整行业路径的场景。

    返回：{1: '一级名称', 2: '二级名称', 3: '三级名称'}

    示例：
        get_industry_hierarchy('025', '025001002001')
        →  {1: '石油石化', 2: '石油化工', 3: '炼油'}
    """
    sql = f"""
    SELECT c_param_code, c_param_name, c_parent_code
    FROM tytdata.tb_dict_params
    WHERE c_param_type = '{param_type}'
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql)

    # 构建 code -> (name, parent) 映射
    code_map = {
        row['c_param_code']: (row['c_param_name'], row['c_parent_code'])
        for _, row in df.iterrows()
    }

    # 从末级向上回溯
    path = []
    current = leaf_code
    while current and current in code_map:
        name, parent = code_map[current]
        path.append(name)
        current = parent

    path.reverse()
    return dict(enumerate(path, 1))
```

---

## 同步脚本

| 文件         | 说明                    |
|------------|-----------------------|
| insert.py  | 全量同步脚本，从Oracle读取写入Doris |

运行方式：

```bash
python insert.py
```
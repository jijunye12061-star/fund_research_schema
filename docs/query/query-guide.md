# 应用侧取数规范

本文档面向客户取数/基金筛选场景，对应 `.claude/skills/query/` 工作流。
建表/ETL 相关规范见 `docs/infra/`。

---

## 两种执行模式

| 特征 | 模式 A：直接查询 | 模式 B：生成脚本 |
|------|-----------------|-----------------|
| 典型需求 | "查一下某基金的行业配置" | "筛选满足 xxx 条件的基金" |
| 结果规模 | ≤ 200 行，对话内能看清 | 多表关联、数据量大、需要 Excel 交付 |
| 执行方式 | curl API，对话内展示结果 | 生成 `scripts/xxx.py`，用户自己运行 |
| 输出落点 | 无文件 | `data/xxx.xlsx` |

---

## 脚本规范（模式 B）

### 任务文件夹结构

每个取数任务独立一个文件夹，格式 `scripts/YYYYMMDD_事项名/`：

```
scripts/
  20260414_高仓位低换手基金筛选/
    query.py        ← 取数脚本
    data/           ← 输出文件（xlsx/csv），不提交 git
    README.md       ← 需求说明文档
  archive/          ← 旧脚本归档
```

### README.md 模板（需求说明）

```markdown
# 事项名称

## 需求背景
[客户/内部需求的背景说明]

## 交付要求
- 筛选条件：...
- 报告期：...
- 输出字段：...

## 输出文件
- `data/xxx.xlsx`

## 备注
[特殊处理、数据质量问题等]
```

### 脚本模板

```python
"""
[一句话说明脚本做什么]

输出列：字段1 | 字段2 | ...
"""
from pathlib import Path
import pandas as pd
from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

# ── 查询参数（按需修改）──────────────────────────────────────
REPORT_DATE = 'YYYY-MM-DD'


def _fetch_xxx(doris: DorisConnector) -> pd.DataFrame:
    """说明"""
    sql = """
    SELECT ...
    FROM tb_xxx f
    JOIN tb_fd_basic_info b ON b.c_fd_code = f.c_fd_code
    WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND f.c_report_date = %s
    """
    return doris.query(sql, REPORT_DATE)


def run():
    with DorisConnector(ENV) as doris:
        df = _fetch_xxx(doris)

    logger.info(f"获取 {len(df)} 行")

    out_path = Path(__file__).parent / 'data' / 'output_name.xlsx'
    out_path.parent.mkdir(exist_ok=True)
    df.to_excel(out_path, index=False)
    logger.info(f"已保存至 {out_path}")
    return df


if __name__ == '__main__':
    run()
```

**与 insert.py 的区别**：
- 有 `ENV = 'dev'`（需要加载数据库配置）
- 不写 `_setup_path()`（无需 DS 调度环境）
- 不写 `run(calc_date)` 签名（无调度参数）
- 输出路径是脚本所在文件夹的 `data/` 子目录（`Path(__file__).parent / 'data'`）

### 批量 IN 查询
```python
sql = "SELECT ... FROM tb_xxx WHERE c_fd_code IN (:code_list)"
doris.query_batch(sql, code_list, **other_params)
```

---

## SQL 约定（摘自业务规则）

| 约定 | 说明 |
|------|------|
| 主代码去重 | `b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL` |
| 全持仓 | `c_style IN ('02', '04')` |
| 前十大持仓 | `c_style IN ('01', '03', '05', '06')` |
| 报告期匹配 | 精确等值 `c_report_date = %s`，禁止 BETWEEN |
| 比例字段 | 百分比存储，5.0 = 5% |
| 报告期→最近交易日 | `SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = %s` |

详见 `docs/infra/database-conventions.md` 和 `.claude/memory/business_rules_fund_data.md`。

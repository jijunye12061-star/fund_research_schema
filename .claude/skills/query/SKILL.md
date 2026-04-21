---
name: query
description: >
  基金研究数据库取数工作流（fund_research_schema 项目专用）。
  当用户提出任何数据查询、取数、数据分析、数据导出、筛选、指标计算等需求时，
  必须使用此 skill，不要自行猜测表结构或字段名。
  触发场景：
  "帮我查 xxx 基金的 yyy 数据"、"取一下最近一期的行业配置"、
  "查某基金的换手率"、"筛选高仓位基金"、"某指标的历史数据"、
  "数据库里有没有 xxx 字段"、"我要看 xxx 表"、"帮我找满足 xxx 条件的基金"、
  "导出 xxx 数据"、任何涉及从 Doris 或 Oracle 获取数据的场景。
---

# Query — 基金数据库取数工作流

## Step 0：识别场景

**收到需求后先判断两个维度，再决定路径：**

### 维度一：是否客户需求？

| 特征 | 客户需求 | 内部查数 |
|------|---------|---------|
| 用户说明 | 明确说"客户需求" | 未提及，或说"自己看看" |
| 输出格式 | 楷体格式 Excel + 备注页 | 直接 `to_excel`，无格式 |
| 执行前 | **必须先确认细节**（见下方清单） | 可直接执行 |

**客户需求确认清单**（逐项与用户对齐，确认后再写代码）：
- [ ] 基金范围：类型（二级债基/主动权益/…）、成立时间要求、运营状态
- [ ] 主代码去重：通常必须，特殊表（如持有人结构）除外
- [ ] 报告期：最新期 or 指定期，季报 or 半年报/年报口径
- [ ] 数据内容：拉什么字段、哪几类指标、是否需要辅助字段（如总仓位）
- [ ] 筛选条件：门槛值 or 全量输出
- [ ] 排序方式：按什么降序/升序
- [ ] 输出文件名

### 维度二：直接查询 or 生成脚本？

| 特征 | 模式 A：直接查询 | 模式 B：生成脚本 |
|------|----------------|----------------|
| 典型需求 | "查一下某基金的行业配置" | 多表关联、需要 Excel 交付 |
| 结果规模 | ≤ 200 行，对话里能看清 | 数据量大或需落文件 |
| 执行方式 | MetabaseConnector 现场执行，对话内展示 | 生成 `analysis/YYYYMMDD_xxx/query.py` |

有歧义时问一句："你是要我这里直接查给你看，还是帮你生成脚本导出 Excel？"

---

## Step 1：表探查（两种模式都要做）

1. 读 `docs/infra/table-catalog.md`，识别相关表（通常 1-3 张）
2. 读对应 `tables/tb_xxx/SPEC.md`，确认字段名、枚举值、JOIN 关系和 SQL 示例
3. 字段含义仍不确定时，用 MetabaseConnector 抽样：
   ```python
   # 在 bash 里执行
   python -c "
   from utils.metabase import MetabaseConnector
   with MetabaseConnector() as mb:           # DB_ORACLE=39 切换 Oracle
       df = mb.query('SELECT * FROM tytdata.tb_xxx LIMIT 10')
       print(df.to_string())
   "
   ```
4. 读 `.claude/skills/query/memory/MEMORY.md`，有已知坑直接应用

---

## 模式 A：直接查询

用 MetabaseConnector 在 bash 里执行，对话内展示实际行数 + 关键列。

### SQL 规范

```python
from utils.metabase import MetabaseConnector

with MetabaseConnector() as mb:
    df = mb.query("""
    SELECT ...
    FROM tytdata.tb_xxx f
    JOIN tytdata.tb_fd_basic_info b ON b.c_fd_code = f.c_fd_code
    WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND f.c_report_date = :report_date
    """, report_date='2025-12-31')
    print(f"{len(df)} 行")
    print(df.head(10).to_string())
```

**必须遵守的约定：**

- SQL 用 `:param_name` 命名绑定变量，对应 `mb.query(sql, param_name=value)`
- 涉及基金维度时，必须主代码去重：
  ```sql
  JOIN tytdata.tb_fd_basic_info b ON b.c_fd_code = f.c_fd_code
  WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
  ```
- c_style 互斥，不能混查：全持仓 `IN ('02','04')`；前十大 `IN ('01','03','05','06')`
- 报告期精确匹配：`c_report_date = :date`，禁止 BETWEEN
- MetabaseConnector 自动分页（单次 2000 行限制），超出时自动翻页透明处理
- 数据量大时优先在 SQL 层聚合，而非拉明细到 Python

---

## 模式 B：生成脚本

生成完整可运行的 Python 脚本，保存到 `analysis/` 目录，**Claude 负责执行并验证结果**。

### 文件夹结构

```
analysis/
  20260421_二级债基有色煤炭商业航天持仓筛选/
    query.py        ← 取数脚本（Claude 执行验证）
    data/           ← 输出文件
    README.md       ← 需求说明
```

### 脚本模板（内部查数）

```python
"""[一句话说明] 输出列：字段1 | 字段2 | ..."""
from pathlib import Path
import pandas as pd
from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

REPORT_DATE = 'YYYY-MM-DD'


def _fetch_xxx(doris: DorisConnector) -> pd.DataFrame:
    sql = """
    SELECT ...
    FROM tytdata.tb_xxx f
    JOIN tytdata.tb_fd_basic_info b ON b.c_fd_code = f.c_fd_code
    WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND f.c_report_date = :report_date
    """
    return doris.query(sql, report_date=REPORT_DATE)


def run():
    with DorisConnector(ENV) as doris:
        df = _fetch_xxx(doris)
    logger.info(f"获取 {len(df)} 行")
    out = Path(__file__).parent / 'data' / 'output.xlsx'
    out.parent.mkdir(exist_ok=True)
    df.to_excel(out, index=False)          # 内部查数：直接输出，无格式
    logger.info(f"已保存至 {out}")
    return df

if __name__ == '__main__':
    run()
```

### 脚本模板（客户需求）

客户需求在内部模板基础上，输出替换为 `to_client_excel`，并增加备注页。

```python
"""[一句话说明] 输出列：字段1 | 字段2 | ..."""
from pathlib import Path
import pandas as pd
from utils.db_connector import DorisConnector
from utils.excel_writer import to_client_excel
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

REPORT_DATE = 'YYYY-MM-DD'


def _fetch_xxx(doris: DorisConnector) -> pd.DataFrame:
    sql = """..."""
    return doris.query(sql, report_date=REPORT_DATE)


def _build_notes() -> pd.DataFrame:
    """备注内容：仅业务逻辑说明，不涉及字段名/表名/数据库术语"""
    return pd.DataFrame([
        ['报告期',   'YYYY年年报/季报（YYYY-MM-DD），使用全持仓 or 前十大重仓'],
        ['基金范围', '...，成立满X个月且正常运营，按主代码去重'],
        ['xxx 来源', '按...分类，基于A股持仓'],
        ['权重口径', '各类持仓市值占基金净值总额的比例（%）'],
        ['筛选条件', '...'],
    ], columns=['说明项', '内容'])


def run():
    with DorisConnector(ENV) as doris:
        df = _fetch_xxx(doris)
    logger.info(f"获取 {len(df)} 行")

    out = Path(__file__).parent / 'data' / 'output.xlsx'
    to_client_excel(
        path=out,
        result_df=df,
        notes_df=_build_notes(),
        col_widths={'A': 11, 'B': 42, 'C': 24, ...},   # 按实际列宽填写
        num_cols=['D', 'E', 'F'],                         # 数字列
        result_sheet='筛选结果',
    )
    logger.info(f"已保存至 {out}")
    return df

if __name__ == '__main__':
    run()
```

### 执行流程

1. 生成脚本后，Claude **用 MetabaseConnector 直接执行核心查询验证逻辑**
2. 数据量在 Metabase 限制内（或 SQL 层已聚合）→ 直接生成 Excel 到 `data/`
3. 数据量超限且无法 SQL 聚合 → 告知用户需要 `python query.py` 走 DorisConnector

### README.md 模板

```markdown
# 事项名称

## 需求背景
[背景说明]

## 交付要求
- 基金范围：...
- 报告期：...
- 输出字段：...
- 筛选条件：...

## 输出文件
- `data/xxx.xlsx`（持仓筛选结果 + 备注）

## 备注
[特殊处理说明]
```

---

## Step 最后：任务收尾

1. **有无值得保存的经验**：字段陷阱/JOIN 坑/枚举值特殊情况 → 写入 `.claude/skills/query/memory/`
2. **不值得保存的**：具体 SQL、参数值、结果数字、通用知识

---

## 快速参考

| 约定 | 说明 |
|------|------|
| 比例字段 | 百分比存储，5.0 = 5% |
| 报告期匹配 | 精确等值，禁止 BETWEEN |
| 主代码去重 | `c_init_code = c_fd_code OR c_init_code IS NULL` |
| 全持仓 | `c_style IN ('02', '04')` |
| 前十大持仓 | `c_style IN ('01', '03', '05', '06')` |
| 报告期→最近交易日 | `SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = :date` |
| SQL 绑定变量 | DorisConnector/MetabaseConnector 统一用 `:param_name` + `**kwargs` |
| MetabaseConnector | `from utils.metabase import MetabaseConnector`，自动分页，上限前自动翻页 |
| 客户 Excel 输出 | `from utils.excel_writer import to_client_excel` |
| 内部 Excel 输出 | `df.to_excel(path, index=False)` |

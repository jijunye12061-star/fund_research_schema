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

## Step 0：判断模式

**收到需求后先判断模式，再执行。** 两条路径完全不同：

| 特征 | 模式 A：直接查询 | 模式 B：生成脚本 |
|------|-----------------|-----------------|
| 典型需求 | "查一下某基金的行业配置" | "筛选出满足xxx条件的基金" |
| 结果规模 | 预计 ≤ 200 行，对话里能看清 | 多表关联、数据量大、需要 Excel 交付 |
| 执行方式 | 直接 curl API，对话内展示结果 | 生成 `scripts/xxx.py`，告知用户路径和运行方式 |
| 用户操作 | 无需操作 | 用户自己 `python scripts/xxx.py`，结果落 `data/` |

有歧义时问一句："你是要我这里直接查给你看，还是帮你生成脚本导出 Excel？"

---

## Step 1：表探查（两种模式都要做）

1. 读 `docs/infra/table-catalog.md`，识别相关表（通常 1-3 张）
2. 读对应 `tables/tb_xxx/SPEC.md`，确认字段名、枚举值、JOIN 关系和 SQL 示例
3. 字段含义仍不确定时，用 curl 抽样 5-10 行：
   ```bash
   curl -X POST https://tytapitest.1234567.com.cn/ty/sql \
     -H "Authorization: Bearer $REMOTE_SQL_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"sql": "SELECT * FROM tb_xxx LIMIT 10"}'
   ```
4. 读 `.claude/skills/query/memory/MEMORY.md`，有已知坑直接应用，无需重复踩

---

## 模式 A：直接查询

在对话里 curl 执行，展示实际行数 + 前 10 行关键列。

### SQL 规范

```bash
# Doris（默认）— 绑定变量用 %s
curl -X POST https://tytapitest.1234567.com.cn/ty/sql \
  -H "Authorization: Bearer $REMOTE_SQL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT ... WHERE c_fd_code = %s LIMIT 100", "params": ["000001"]}'

# Oracle — 绑定变量用 :1
curl -X POST https://tytapitest.1234567.com.cn/ty/sql \
  -H "Authorization: Bearer $REMOTE_SQL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT ... WHERE FUNDCODE = :1 AND ROWNUM <= 5", "db": "oracle", "params": ["000001"]}'
```

**必须遵守的约定：**

- 禁止 f-string 拼接参数，只用绑定变量
- 涉及基金维度时，必须主代码去重：
  ```sql
  JOIN tb_fd_basic_info b ON b.c_fd_code = f.c_fd_code
  WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
  ```
- c_style 互斥，不能混查：全持仓 `IN ('02','04')`；前十大 `IN ('01','03','05','06')`
- 报告期精确匹配：`c_report_date = %s`，禁止 BETWEEN
- API 最多返回 5000 行，数据量大时先聚合

结果不符预期时，说明排查方向（字段单位？过滤条件？枚举值？）再试。

---

## 模式 B：生成脚本

生成完整可运行的 Python 脚本，保存到 `scripts/` 目录。

### 文件夹结构

每个取数任务独立一个文件夹，格式 `scripts/YYYYMMDD_事项名/`：

```
scripts/
  20260414_高仓位低换手基金筛选/
    query.py        ← 取数脚本
    data/           ← 输出文件（xlsx/csv）
    README.md       ← 需求说明文档
  20260410_中原农险赛道池打分/
    ...
  archive/          ← 旧的扁平脚本归档
```

**README.md 模板**（需求说明，写清楚背景和交付要求）：

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

> **与 insert.py 的区别**：取数脚本有 `ENV='dev'`，但不写 `_setup_path()`（无需 DS 环境），不写 `run(calc_date)` 签名（无调度参数），输出路径指向脚本所在文件夹的 `data/` 子目录。

**批量 IN 查询**（需要按列表过滤时）：
```python
# SQL 中写 IN (:code_list)
sql = "SELECT ... FROM tb_xxx WHERE c_fd_code IN (:code_list)"
doris.query_batch(sql, code_list, **other_params)
```

### 生成完毕后告知用户

```
任务文件夹：scripts/YYYYMMDD_事项名/
├── query.py        ← 取数脚本（需要修改第 XX 行的 REPORT_DATE）
├── data/           ← 运行后输出到这里
└── README.md       ← 需求说明（已填写）

运行方式：python scripts/YYYYMMDD_事项名/query.py
```

---

## Step 最后：任务收尾

取数完成后主动检查，不要等用户提：

1. **有无值得保存的经验**：字段陷阱/特殊过滤/JOIN 坑 → 写入 `.claude/skills/query/memory/`，更新 `MEMORY.md`
2. **不值得保存的**：具体 SQL、参数值、结果数字、通用 Python/SQL 知识

如果用户需要更全面的会话收尾（多个任务、跨场景），可输入 `/wrap`。

---

## 快速参考

| 约定 | 说明 |
|------|------|
| 比例字段 | 百分比存储，5.0 = 5% |
| 报告期匹配 | 精确等值，禁止 BETWEEN |
| 主代码去重 | `c_init_code = c_fd_code OR c_init_code IS NULL` |
| 全持仓 | `c_style IN ('02', '04')` |
| 前十大持仓 | `c_style IN ('01', '03', '05', '06')` |
| 报告期→最近交易日 | `SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = %s` |

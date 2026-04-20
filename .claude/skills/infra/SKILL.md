---
name: infra
description: >
  基金研究数据平台基建工作流（fund_research_schema 项目专用）。
  当用户提出任何建表、加字段、改 schema、建视图、写 insert.py、
  调整调度、补历史数据、修改 ETL 逻辑等需求时，必须使用此 skill。
  触发场景：
  "建一张 xxx 表"、"给 tb_xxx 加字段"、"改 DDL"、"写 insert.py"、
  "建视图"、"提交 DBA"、"调度怎么配"、"补一下历史数据"、
  任何涉及 tables/ 目录、schema.sql、view.sql、SPEC.md 的操作。
---

# Infra — 基建工作流

## 加载规范

收到建表/ETL 需求后，先读以下文档（按需选读）：

- `docs/infra/table-catalog.md` — 现有 26 张表总览，判断是否重复建设
- `docs/infra/coding-standards.md` — 命名/风格/ETL 模式
- `docs/infra/database-conventions.md` — 字段约定、枚举值、Doris DDL 要点
- `docs/infra/scheduling-guide.md` — 调度时机、should_run、双触发规则
- `docs/infra/etl-guide.md` — Oracle 取数注意事项
- `docs/infra/view-mapping-guide.md` — 视图型表的 Oracle→Doris 映射约定
- `.claude/memory/project_status.md` — 当前建表进度，避免重复讨论
- `.claude/memory/feedback_dev.md` — 历史踩坑，直接复用

---

## 完整上线流程

从需求到调度，全程按以下阶段推进。**Claude 负责代码和验证，用户负责在数据库环境执行和上 DS**。

### 阶段一：方案讨论

```
1. 需求提出   说明表名、数据来源、更新频率、业务用途
2. 方案确认   表类型（视图/物化/计算）、主键、字段列表、分区/分桶策略
3. 数据探查   用远程 SQL API 查源表样本，确认字段含义和枚举值
```

产出：双方对齐方案，无歧义再动手写代码。

### 阶段二：开发

```
4. 编写产出   schema.sql / view.sql → SPEC.md → insert.py
★  更新目录   在 docs/infra/table-catalog.md 对应层级加一行（表名+说明+频率）
5. 本地验证   用户在数据库环境执行 insert.py，跑一两个日期
6. 数据质量   Claude 用远程 SQL 抽样检查写入数据（行数/字段值/边界case）
```

> catalog 只需一行：表名、一句话说明、更新频率。依赖关系写在 SPEC.md 里，不写进 catalog。

### 阶段三：代码 Review（上线前必做）

在补数和上调度之前，Claude 主动对 insert.py 做以下检查：

**幂等性**
- 相同 `calc_date` 重跑，不会产生重复数据（UNIQUE KEY 覆盖写入）
- `DELETE + INSERT` 或 `INSERT OVERWRITE` 的边界是否正确

**日期逻辑**
- `run()` 的日期范围处理是否正确（含头含尾？跨月？）
- `should_run()` 门控条件是否匹配调度频率

**数据完整性**
- 源表字段是否有 NULL 处理
- JOIN 条件是否会意外扩大或缩小行数
- 比例字段单位（百分比 vs 小数）

**DS 兼容性**
- `_setup_path()` 在文件最顶部、import 之前调用
- `__main__` 的 DS 调度块使用 `"$[yyyyMMdd-1]"` 模板变量 + 字符串切片转换日期格式
- ENV 使用参数注入 + 本地 fallback：`_env = "${db_env}"; ENV = _env if not _env.startswith("${") else "dev"`

### 阶段四：补数

```
7. 确认起始日期   与用户对齐历史数据起点（见 docs/infra/table-catalog.md 的"历史起点"列）
8. 用户执行补数   在数据库环境循环跑历史期，或用 backfill 脚本
9. Claude 抽查    抽 2-3 个历史报告期验证数据质量
```

### 阶段五：上 DS 调度

由用户操作，Claude 提供参数确认：

```
10. 复制 insert.py 代码到 DS 资源中心对应路径
11. 配置调度参数：
    - 脚本路径（确认与 _setup_path 的目录层级一致）
    - 入参格式（DS 传入 yyyyMMdd，parse_biz_date 转换为 yyyy-MM-dd）
    - 触发时机（见 docs/infra/scheduling-guide.md）
12. 手动触发一次，观察日志
13. Claude 验证首次调度写入的数据
```

---

## insert.py 标准结构

```python
"""一句话说明这张表做什么"""
import sys
from pathlib import Path


def _setup_path():
    """兼容本地和 DS 环境的路径适配。
    
    DS 调度器从自己的工作目录执行脚本，项目根不在 sys.path，
    需要在 import utils 之前手动插入。
    优先向上遍历找 utils/db_connector.py，兜底使用 DS 固定路径。
    不能抽到公共模块——_setup_path 依赖 __file__ 定位，抽出去后
    __file__ 会指向 utils/ 内部，层级计算就会错误。
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return
    raise RuntimeError("找不到 utils 目录，请检查路径配置")


_setup_path()  # 必须在所有 utils import 之前调用

from utils.db_connector import OracleConnector, DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"  # DS 注入 db_env；本地默认 dev


def run(calc_date: str):
    """主入口，calc_date 格式 %Y-%m-%d"""
    ...


if __name__ == '__main__':
    # ── DS 调度模式 ──────────────────────────────────────────────────
    raw = "$[yyyyMMdd-1]"
    run(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）────────────────
    # run('2026-01-01')
```

**季度/半年度表**（如标签表）用 `run(report_date: str)` + `should_run()` 门控：

```python
from utils.common import should_run, ReportFreq, generate_report_dates

if __name__ == '__main__':
    # ── DS 调度模式 ──────────────────────────────────────────────────
    raw = "$[yyyyMMdd-1]"
    calc_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
    if ok:
        logger.info(f"触发执行，报告期={report_date}")
        run(report_date)
    else:
        logger.info(f"非披露窗口，跳过（calc_date={calc_date}）")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）────────────────
    # for report_date in generate_report_dates('2025-12-31', N):
    #     run(report_date)
```

---

## Doris DDL 要点（快速参考）

DDL 块顺序：`UNIQUE KEY → COMMENT → PARTITION BY → DISTRIBUTED BY → PROPERTIES`

- `COMMENT` 必须含 `[机构研究]`
- 不加反引号、不加显式 NULL、必须加 `tytdata.` schema 前缀
- UNIQUE KEY：日期列在前（前缀索引优化）
- DISTRIBUTED BY HASH：只用单列
- 桶数：小维度表 1，季度表 3，按月分区大表 1/分区
- PROPERTIES 只保留三项：`replication_allocation`、`storage_format`、`enable_unique_key_merge_on_write`
- 不要在 schema.sql 中写 DROP TABLE（DBA 单独处理）

---

## 远程 SQL 探查

```bash
# Doris测试（db=43）
curl -s -X POST http://metabase.jg/api/dataset \
  -H "X-API-KEY: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"database":43,"type":"native","native":{"template-tags":{},"query":"SELECT * FROM tb_fd_basic_info LIMIT 5"},"parameters":[]}' \
  | python -c "import json,sys; d=json.load(sys.stdin); cols=[c['name'] for c in d['data']['cols']]; [print(dict(zip(cols,r))) for r in d['data']['rows']]"

# Oracle投研通（db=39）
curl -s -X POST http://metabase.jg/api/dataset \
  -H "X-API-KEY: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"database":39,"type":"native","native":{"template-tags":{"owner":{"name":"owner","type":"text"},"tbl":{"name":"tbl","type":"text"}},"query":"SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER={{owner}} AND TABLE_NAME={{tbl}} AND ROWNUM<=5"},"parameters":[{"type":"category","value":"TYTFUND","target":["variable",["template-tag","owner"]]},{"type":"category","value":"FUND_IV_STOCKINVESTO","target":["variable",["template-tag","tbl"]]}]}' \
  | python -c "import json,sys; d=json.load(sys.stdin); cols=[c['name'] for c in d['data']['cols']]; [print(dict(zip(cols,r))) for r in d['data']['rows']]"
```

- 优先查 Doris（更快，不影响 Oracle 生产库）
- 写入（Stream Load）无法远程测试，逻辑验证即可

---

## 任务收尾（每次完成后主动检查）

完成建表/ETL 任务后，主动判断以下几点，不要等用户提：

1. **catalog 是否更新了**：新表有没有加进 `docs/infra/table-catalog.md`
2. **SPEC 是否完整**：字段说明/枚举值/依赖/起点是否写清楚
3. **project_status 是否需要更新**：表已上线或进入新阶段，更新 `.claude/memory/project_status.md`
4. **有无值得保存的经验**：踩到非显而易见的坑（字段单位/枚举值/JOIN 陷阱）则写入 `.claude/memory/feedback_dev.md`

如果用户没有明确说"结束了"，但任务已进入收尾阶段，主动说一句："这次有没有什么需要记录下来的经验？"

---

## 禁止事项

- 不要修改 `utils/db_connector.py`，除非明确讨论
- 不要用 `to_sql` 写入 Doris（用 `doris.insert()`）
- 不要把 `_setup_path()` 抽到公共模块（见函数注释）
- 不要在 insert.py 里加 try-except
- 不要写超过 3 层嵌套，用 early return

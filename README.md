# 基金研究数据库项目

## 一、项目概述

基于 Doris 的基金研究数据库，包含两类数据来源：

- **同步表**：从 Oracle TYTFUND 通过视图映射的原始数据
- **计算表**：基于原始数据用 Python 计算的衍生指标

数据更新通过调度平台（DolphinScheduler）定时触发。

---

## 二、项目结构

```
fund_research_schema/
├── config/
│   └── database.yaml          # 数据库连接配置（Oracle + Doris，gitignored）
│
├── utils/
│   ├── db_connector.py        # OracleConnector / DorisConnector
│   ├── common.py              # 公共函数
│   └── __init__.py
│
├── tables/
│   ├── tb_fd_basic_info/      # 物化表示例（schema.sql + insert.py + SPEC.md）
│   ├── tb_fd_portfolio_bd/    # 视图表示例（view.sql + SPEC.md）
│   └── ...
│
└── docs/                      # 项目规范文档
```

---

## 三、核心模块说明

> 详细用法见 [`docs/etl-guide.md`](docs/etl-guide.md)

| 模块 | 说明 |
|------|------|
| `OracleConnector` | 查询 Oracle TYTFUND，支持 `query()` / `query_batch()` |
| `DorisConnector` | 查询和写入 Doris，支持 `query()` / `query_batch()` / `insert()` |
| `get_trade_calendar(start, end)` | 获取交易日历，返回 DatetimeIndex |
| `get_active_funds(calc_date)` | 获取截至指定日期存续的基金列表 |
| `get_last_quarter_end(calc_date)` | 获取上一季末日期 |

---

## 四、表目录规范

每张表一个文件夹，按类型包含以下文件：

| 表类型 | 文件 | 说明 |
|--------|------|------|
| 视图型 | `view.sql` + `SPEC.md` | Oracle 实时映射，无需调度 |
| 物化型 | `schema.sql` + `insert.py` + `SPEC.md` | 定期同步，含数据清洗 |
| 计算型 | `schema.sql` + `insert.py` + `SPEC.md` | 基于 Doris 已有数据计算衍生指标 |

> 命名规范和建表规范见 [`docs/database-conventions.md`](docs/database-conventions.md)

> 代码规范见 [`docs/coding-standards.md`](docs/coding-standards.md)

---

## 五、新表添加流程

**视图型**：写 `view.sql` + `SPEC.md` → 提交 DBA 执行

**物化/计算型**：

1. 写 `schema.sql`（提交 DBA 建表）、`insert.py`、`SPEC.md`
2. 本地测试：`python tables/tb_xxx/insert.py`
3. 调度平台注册任务，调用 `run(calc_date)`

---

**维护者**: 季俊晔  
**最后更新**: 2026-04-03

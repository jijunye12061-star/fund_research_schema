# 项目结构说明

> fund_research_schema 项目的目录组织与文件约定。

## 目录结构

```
fund_research_schema/
├── config/
│   ├── database.yaml           # 数据库配置（gitignored）
│   ├── database.yaml.example   # 配置模板（已提交）
│   └── __init__.py
│
├── tables/                     # 表模块集合，一表一文件夹
│   ├── tb_fd_basic_info/
│   │   ├── schema.sql          # 建表语句
│   │   ├── insert.py           # 数据同步/计算脚本
│   │   └── SPEC.md             # 表说明文档
│   │
│   ├── tb_fd_portfolio_stk/
│   │   ├── view.sql            # 视图定义（Oracle→Doris映射）
│   │   └── SPEC.md
│   │
│   └── ...
│
├── utils/                      # 通用工具
│   ├── __init__.py
│   ├── db_connector.py         # OracleConnector / DorisConnector
│   └── common.py               # get_trade_calendar, get_active_funds 等
│
├── docs/
│   ├── infra/                  # 基建规范（建表/ETL/调度/命名）
│   │   ├── coding-standards.md
│   │   ├── database-conventions.md
│   │   └── ...
│   ├── query/                  # 取数规范
│   │   └── query-guide.md
│   └── shared/                 # 共享领域知识
│       └── equity-fund-labels.md
│
├── .gitignore
└── README.md
```

## 表模块分类

### 视图型（Oracle 实时映射）

适用于简单字段映射，无需调度，实时同步。

```
tables/tb_fd_portfolio_stk/
├── view.sql          # CREATE VIEW 语句
└── SPEC.md
```

### 物化型（定期同步）

适用于需要数据清洗、转换、多表 JOIN 的场景。

```
tables/tb_fd_basic_info/
├── schema.sql        # CREATE TABLE 语句
├── insert.py         # 同步脚本
└── SPEC.md
```

### 计算型（自建衍生指标）

适用于从已有数据计算新指标。

```
tables/tb_fd_perform_abs/
├── schema.sql        # CREATE TABLE 语句
├── insert.py         # 计算脚本（计算逻辑注释在此）
└── SPEC.md
```

## SPEC.md 内容规范

SPEC 以**取数为主定位**，服务于 query skill 生成 SQL / 分析代码。

**必须包含：**
- 基本信息（主键 / 更新频率 / 适用范围）
- 字段清单（名 / 类型 / 注释 / 单位）
- 枚举值（如有）
- **注意事项**（取数易踩的坑：去重条件、必须逐期查、NULL 场景等）
- 使用示例（1–2 个典型 SQL）

**不写在 SPEC 里：**
- Oracle 源表 JOIN 条件 / 计算步骤细节 → 放 insert.py 注释
- 下游依赖（谁消费了这张表）
- 历史补数命令 / DS 调度代码

计算型表可在"基本信息"末尾加一行 `**依赖表**：xxx / xxx`，供追溯上游时用。


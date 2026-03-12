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
├── docs/                       # 项目级文档
│   ├── coding-standards.md
│   ├── database-conventions.md
│   └── ...
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
├── insert.py         # 计算脚本
└── SPEC.md           # 需详细说明计算逻辑
```

## SPEC.md 模板

```markdown
# tb_xxx - 表中文名

## 基本信息
- **主键**: (c_trade_date, c_fd_code)
- **表类型**: 物化型 / 视图型 / 计算型
- **更新频率**: 日度 / 季度 / 全量

## 数据来源
- **Oracle表**: TYTFUND.XXX（主表）
- **更新逻辑**: 全量替换 / 增量更新
- **过滤条件**: WHERE EISDEL = '0'（如有）

## 数据质量
- 特殊处理说明
- 默认值规则

## 字段清单
| 字段名 | 类型 | 注释 | 说明 |
|--------|------|------|------|
| c_fd_code | VARCHAR(20) | 基金代码 | 六位代码 |

## 枚举值（如有）
| 代码 | 名称 |
|------|------|
| 01   | 一季报 |

## 使用示例
（SQL查询示例）
```

## 安全要求

- `config/database.yaml` **绝不提交**，已在 `.gitignore` 中
- 提交 `database.yaml.example` 作为模板
- 历史中曾暴露凭据，建议轮换密码

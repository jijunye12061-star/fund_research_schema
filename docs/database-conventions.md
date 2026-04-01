# 数据库命名与建表规范

> 适用于 Doris (tytdata schema) 和 Oracle (TYTFUND schema) 间的数据建设。

## 命名规则

### 基本要求

- 以字母开头，仅含英文字母、数字和下划线
- 长度 ≤ 30 字符
- 统一使用英文缩写（不中英混杂）
- 禁用数据库保留关键字

### 表名结构

格式：`tb_{业务模块}_{实体名称}_{附加区别}`

```
tb_fd_perform_abs
│  │  │        └── 附加区别: 绝对指标
│  │  └─────────── 实体名称: 业绩表现
│  └────────────── 业务模块: 基金
└───────────────── 类型: table
```

### 固定业务简称

| 业务对象  | 简称       | 示例                 |
|-------|----------|--------------------|
| 基金    | fd       | tb_fd_nav_daily    |
| 股票    | stk      | tb_stk_quote_daily |
| 指数    | idx      | tb_idx_quote_daily |
| 债券    | bd       | tb_fd_portfolio_bd |
| 配置/字典 | cfg/dict | tb_cfg_risk_factor |
| 标签    | tag      | tb_fd_tag_bd_style |

市场后缀：A股默认不加，港股加 `_hk`，美股加 `_us`。
示例：`tb_stk_quote_daily`（A股）、`tb_stk_quote_daily_hk`（港股）

### 字段命名

所有字段统一 `c_` 前缀：

**通用字段**

| 字段名           | 注释   | 说明                                         |
|---------------|------|--------------------------------------------|
| c_id          | 主键   | 自增主键（如需要）                                  |
| c_updatetime  | 更新时间 | `DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6)` |
| c_trade_date  | 交易日  |                                            |
| c_report_date | 报告期  | 季报截止日                                      |
| c_notice_date | 披露日期 |                                            |

**基金字段**

| 字段名          | 注释         |
|--------------|------------|
| c_fd_code    | 基金代码（不含后缀） |
| c_inner_code | 内码（唯一值）    |
| c_short_name | 基金简称       |
| c_full_name  | 基金全称       |

**股票字段**

| 字段名          | 注释   |
|--------------|------|
| c_stk_code   | 股票代码 |
| c_inner_code | 内码   |
| c_short_name | 股票简称 |

**指数字段**

| 字段名          | 注释   |
|--------------|------|
| c_idx_code   | 指数代码 |
| c_inner_code | 内码   |
| c_short_name | 指数简称 |

**命名约定**

| 后缀/前缀  | 含义   | 示例                     |
|--------|------|------------------------|
| c_is_  | 布尔字段 | c_is_st、c_is_stat      |
| _mv    | 市值   | c_float_mv、c_total_mv  |
| _ratio | 百分比  | c_nav_ratio、c_eq_ratio |

---

## Doris 建表规范

### DDL 格式统一要求

以下格式规则**所有新建表必须遵守**，存量表后续逐步统一：

| 项目            | 规范                 | 说明                                                                   |
|---------------|--------------------|----------------------------------------------------------------------|
| 反引号           | **不加**             | `c_fd_code` 而非 `` `c_fd_code` ``                                     |
| 显式 NULL       | **不加**             | `DATE COMMENT '...'` 而非 `DATE NULL COMMENT '...'`（Doris 默认 nullable） |
| schema 前缀     | **必须加** `tytdata.` | `CREATE TABLE tytdata.tb_xxx`                                        |
| DROP TABLE    | **不加**             | 建表语句不含 DROP，DBA 单独处理                                                 |
| TABLE COMMENT | **必须加** `[机构研究]`   | `COMMENT '表中文名[机构研究]'`                                               |
| 关键字大写         | **统一大写**           | `DATE`、`DATETIME(6)`、`DECIMAL`、`VARCHAR`                             |
| 头部注释          | **统一分隔线格式**        | 见下方模板                                                                |

### DECIMAL 精度统一

| 用途      | 类型              | 示例                      |
|---------|-----------------|-------------------------|
| 百分比/权重  | `DECIMAL(10,4)` | c_hk_ratio_avg、c_weight |
| 金额（亿元）  | `DECIMAL(20,4)` | c_total_mv、c_hold_value |
| 收益率（小数） | `DECIMAL(18,6)` | c_return_1d             |
| 评分/得分   | `DECIMAL(10,4)` | c_size_score            |

> 之前部分表使用了 `DECIMAL(8,4)`，整数位仅 4 位（最大 9999.9999%），对百分比够用但余量不足。新表统一用 `DECIMAL(10,4)`
> ，存量表维持不改（兼容性优先）。

### UNIQUE KEY 排列

DATE 类型字段放在最前面，利用前缀索引加速日期范围查询：

```sql
-- ✅ 正确：日期在前
UNIQUE KEY (c_trade_date, c_fd_code)

-- ❌ 错误：字符串在前
UNIQUE KEY (c_fd_code, c_trade_date)
```

无日期字段的维度表（如 basic_info）例外，直接用业务主键。

### DISTRIBUTED BY HASH

**只用单列**，选区分度最高的字段（通常是代码字段）：

```sql
-- ✅ 正确
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3

-- ❌ 错误：多列 HASH 无必要且增加复杂度
DISTRIBUTED BY HASH(c_fd_code, c_report_date) BUCKETS 3
```

### 桶数（Bucket）设定

| 表类型               | 桶数      | 示例                                |
|-------------------|---------|-----------------------------------|
| 单主键小表（万级以下）       | 1 桶     | tb_fd_basic_info、tb_dict_params   |
| 中等数据量（季度更新，万~十万级） | 3 桶     | tb_fd_category、tb_fd_tag_* 系列     |
| 按月分区大表（日频，百万级+）   | 每分区 1 桶 | tb_fd_perform_abs、tb_stk_industry |

### 分区策略

**是否分区的判断标准**：

| 条件                     | 分区 | 不分区 |
|------------------------|----|-----|
| 有 DATE 类型主键 + 数据持续增长   | ✅  |     |
| 静态维度表（basic_info）/ 字典表 |    | ✅   |
| 季度更新的标签表（数据量适中）        | 可选 | 可选  |

> 季度标签表（如 tag_* 系列）数据量较小，分区与否均可。**但同类表应保持一致**——要么全部标签表都分区，要么都不分区。当前建议：*
*标签表统一不分区**，简化管理。

**分区参数统一**（用于需要分区的表）：

```sql
PARTITION BY RANGE(c_trade_date) ()
-- 动态分区参数
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "MONTH",
"dynamic_partition.start" = "-150",          -- 统一用 -150（约12.5年历史）
"dynamic_partition.end" = "3",
"dynamic_partition.prefix" = "p",
"dynamic_partition.buckets" = "1",           -- 分区内桶数
"dynamic_partition.create_history_partition" = "true"
```

> 之前出现过 `-60`、`-150`、`-2147483648` 三种值。统一用 `-150`，覆盖 2013 年至今的数据足够，避免 INT_MIN 创建过多空分区。

### PROPERTIES 精简

只保留三项核心属性，不加 DBA 自动生成的默认项：

```sql
PROPERTIES
( "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true");
```

> `is_being_synced`、`storage_medium`、`light_schema_change`、`disable_auto_compaction`、`enable_single_replica_compaction`
> 等均为 Doris 默认值或 DBA 按需调整项，**schema.sql 中不写**。

---

## 标准建表模板

### 模板A：无分区表（维度表/标签表/字典表）

```sql
-- ============================================================
-- 表中文名
-- 补充说明（如数据来源、更新频率等）
-- ============================================================
CREATE TABLE tytdata.tb_xxx
(
    c_fd_code    VARCHAR(20) COMMENT '基金代码',
    c_short_name VARCHAR(100) COMMENT '基金简称',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP UNIQUE KEY (c_fd_code)
COMMENT '表中文名[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
```

### 模板B：按月分区表（日频/高频数据）

```sql
-- ============================================================
-- 表中文名
-- 补充说明
-- ============================================================
CREATE TABLE tytdata.tb_xxx
(
    c_trade_date DATE COMMENT '交易日期',
    c_fd_code    VARCHAR(20) COMMENT '基金代码',
    c_value      DECIMAL(10, 4) COMMENT '指标值(%)',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP UNIQUE KEY (c_trade_date, c_fd_code)
COMMENT '表中文名[机构研究]'
PARTITION BY RANGE(c_trade_date) ()
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "MONTH",
    "dynamic_partition.start" = "-150",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1",
    "dynamic_partition.create_history_partition" = "true"
);
```

### DDL 语句块顺序

严格按以下顺序排列（Doris 语法要求 + 可读性）：

```
CREATE TABLE tytdata.表名
(
    字段定义...
) ENGINE = OLAP
UNIQUE KEY (...)
COMMENT '...[机构研究]'
PARTITION BY RANGE(...) ()          -- 可选
DISTRIBUTED BY HASH(...) BUCKETS n
PROPERTIES (...);
```

---

## 研究环境设计原则

- **宽表优先**：一行一记录（entity × date），方便研究查询，避免 pivot
- **存储派生标签**：直接存中文文本（如"高仓位"），研究环境不必过度范式化
- **回撤存正值**：行业标准，百分比存已乘值
- **比例/权重存百分数**：5.0 表示 5%，与 `_ratio` 命名一致

---

## 存量表差异说明

以下差异存在于早期建的表中，后续有机会统一时再改，**新表不允许出现**：

| 差异项                | 涉及表                                          | 处理方式         |
|--------------------|----------------------------------------------|--------------|
| 反引号 `` ` ``        | tb_stk_basic_info、tb_fd_category 等           | 功能无影响，不改     |
| 显式 `NULL`          | tb_fd_ind_weight、tb_fd_category 等            | 功能无影响，不改     |
| `DECIMAL(8,4)`     | tb_fd_ind_weight、tb_fd_tag_stk_region_sector | 不影响现有数据，不改   |
| 多余 PROPERTIES      | tb_stk_basic_info、tb_fd_category             | 功能无影响，不改     |
| `HASH` 双列          | tb_fd_category                               | 功能无影响，不改     |
| COMMENT 缺 `[机构研究]` | tb_fd_tag_bd_style、tb_dict_params            | 下次 ALTER 时补上 |
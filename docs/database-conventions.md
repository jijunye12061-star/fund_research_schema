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

## Doris 建表规范

### UNIQUE KEY 排列

DATE 类型字段放在最前面，利用前缀索引加速日期范围查询：

```sql
-- ✅ 正确：日期在前
UNIQUE KEY (c_trade_date, c_fd_code)

-- ❌ 错误：字符串在前
UNIQUE KEY (c_fd_code, c_trade_date)
```

### 桶数（Bucket）设定

按数据量调整，避免小表过多桶产生小文件：

| 表类型         | 桶数      | 示例                |
|-------------|---------|-------------------|
| 单主键小表（万级）   | 1 桶     | tb_fd_basic_info  |
| 中等数据量（季度更新） | 3 桶     | tb_fd_category    |
| 按月分区大表（日频）  | 每分区 1 桶 | tb_fd_perform_abs |

### 标准建表模板

```sql
CREATE TABLE tb_fd_basic_info
(
    c_fd_code    VARCHAR(20) COMMENT '基金代码',
    c_short_name VARCHAR(100) COMMENT '基金简称',
    c_estabdate  DATE COMMENT '成立日期',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_fd_code)
COMMENT
'基金基础信息表'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
```

### 按月分区模板

```sql
CREATE TABLE tb_fd_perform_abs
(
    c_trade_date DATE COMMENT '交易日期',
    c_fd_code    VARCHAR(20) COMMENT '基金代码',
    c_return_1d  DECIMAL(18, 6) COMMENT '日收益率',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_trade_date, c_fd_code)
COMMENT
'基金绝对收益指标表'
PARTITION BY RANGE(c_trade_date) ()
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "MONTH",
    "dynamic_partition.start" = "-2147483648",
    "dynamic_partition.end" = "2",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1",
    "dynamic_partition.create_history_partition" = "true"
);
```

### 关键特性

- **UNIQUE KEY 自动覆盖**：匹配主键时自动更新，无需显式 DELETE 再 INSERT
- **视图不能加索引**：索引只能建在底层物理表上
- **irdev 账号仅有 DML 权限**（SELECT/INSERT），DDL（CREATE/DROP）需 DBA 执行

## 研究环境设计原则

- **宽表优先**：一行一记录（entity × date），方便研究查询，避免 pivot
- **存储派生标签**：直接存中文文本（如"高仓位"），研究环境不必过度范式化
- **回撤存正值**：行业标准，百分比存已乘值

# 基金研究数据库项目

## 一、项目概述

基于 Doris 的基金研究数据库，包含两类表：

- **同步表**：从 Oracle TYTFUND 通过视图映射的原始数据
- **计算表**：基于原始数据用 Python 计算的衍生指标

数据更新通过调度平台（DolphinScheduler）定时触发。

---

## 二、项目结构

```
fund_research_db/
├── config/
│   └── database.yaml          # 数据库连接配置（Oracle + Doris）
│
├── utils/
│   ├── db_connector.py        # OracleConnector / DorisConnector
│   ├── common.py              # 公共函数
│   └── __init__.py
│
├── tables/
│   ├── tb_fd_basic_info/      # 计算表示例
│   │   ├── schema.sql
│   │   ├── insert.py
│   │   └── SPEC.md
│   │
│   ├── tb_fd_asset_allocation/ # 同步表示例
│   │   ├── view.sql
│   │   └── SPEC.md
│   └── ...
│
└── scripts/                   # 规划中
    ├── deploy_tables.sh       # 批量执行建表语句
    └── generate_catalog.py    # 生成数据字典汇总
```

---

## 三、核心模块说明

### utils/db_connector.py

两个连接器，均使用上下文管理器模式：

```python
from utils.db_connector import OracleConnector, DorisConnector

sql = """"""
# Oracle 查询（支持绑定变量）
with OracleConnector() as oracle:
    df = oracle.query(sql, start_date='2024-01-01', end_date='2024-12-31')
    df = oracle.query_batch(sql, code_list=['000001', '000002'])

# Doris 查询 / 写入
with DorisConnector() as doris:
    df = doris.query(sql, calc_date='2024-12-31')
    result_df = doris.query_batch(sql, code_list=[...], start_date='2024-01-01')
    doris.insert('tb_fd_perform_abs', result_df)  # UNIQUE KEY表自动覆盖
```

> `insert()` 用于所有写入场景。UNIQUE KEY 表遇到重复主键时，Doris 自动执行覆盖更新（merge-on-write）。

### utils/common.py

| 函数                                                | 说明                      |
|---------------------------------------------------|-------------------------|
| `get_trade_calendar(start, end)`                  | 获取交易日历，返回 DatetimeIndex |
| `find_nearest_trade_date(date, dates, direction)` | 查找最近交易日                 |
| `generate_report_dates(last_dt, n)`               | 生成最近 n 个季末日期列表          |
| `get_last_quarter_end(calc_date)`                 | 获取上一季末日期                |
| `get_active_funds(calc_date)`                     | 获取存续基金列表                |
| `safe_divide(num, denom, ...)`                    | 安全除法，避免除零               |

---

## 四、表目录规范

### 同步表（Oracle → Doris 视图映射）

```
tables/tb_xxx/
├── view.sql     # CREATE VIEW 映射语句
└── SPEC.md      # 字段说明、枚举值、使用示例
```

### 计算表（Python 计算）

```
tables/tb_xxx/
├── schema.sql   # CREATE TABLE 建表语句
├── insert.py    # 实现 run(calc_date: str) 主入口
└── SPEC.md      # 字段说明、指标逻辑、使用示例
```

`insert.py` 标准结构：

```python
def run(calc_date: str):
    """主入口，由调度平台调用"""
    data = _get_source_data(calc_date)
    result = _calculate_metrics(data)
    with DorisConnector() as doris:
        doris.insert('tb_xxx', result)


if __name__ == '__main__':
    run('2024-12-31')
```

---

## 五、命名规范

**表名**：`tb_{模块}_{实体}` — 如 `tb_fd_basic_info`、`tb_fd_perform_abs`

**字段名**：统一 `c_` 前缀

- 代码类：`c_fd_code`、`c_stk_code`
- 日期类：`c_trade_date`、`c_report_date`
- 名称类：`c_{属性}_name`
- 比例类：`c_{属性}_ratio`（存储为百分数，如 25.5 表示 25.5%）

**数据类型**：
| 用途 | 类型 |
|------|------|
| 代码 | `VARCHAR(20)` |
| 日期 | `DATE` |
| 百分比 | `DECIMAL(10,4)` |
| 金额 | `DECIMAL(20,4)` |
| 更新时间 | `DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6)` |

**Doris 建表规范**：

- UNIQUE KEY 中 DATE 类型字段放在最前面，利用前缀索引加速日期范围查询
- DISTRIBUTED BY HASH 桶数按数据量设定，避免小表过多桶：
  - 单主键小表（如 basic_info）：1 桶
  - 中等数据量表（如季度更新）：3 桶
  - 按月分区的大表（如日频指标）：每分区 1 桶

---

## 六、代码规范

- 单函数 ≤ 30 行，超过则拆分
- 不写 try-except（研究环境直接报错）
- pandas 向量化优先，避免显式循环
- 类型提示必须有
- SQL 使用绑定变量（`:param`），禁止 f-string 拼接

---

## 七、新表添加流程

**同步表**：写 `view.sql` + `SPEC.md` → 提交给 DBA 执行视图

**计算表**：

1. 写 `schema.sql`、`insert.py`、`SPEC.md`
2. 本地测试：`python tables/tb_xxx/insert.py`
3. 调度平台注册任务，调用 `run(calc_date)`

---

## 八、当前进度

**已实现**

- [x] `utils/db_connector.py` — OracleConnector / DorisConnector
- [x] `utils/common.py` — 基础公共函数
- [x] `tb_fd_basic_info` — 基金基础信息（计算表）
- [x] `tb_fd_asset_allocation` — 基金资产配置（同步表）
- [x] `tb_fd_portfolio_bd` — 债券持仓（同步表）
- [x] `tb_fd_category` — 基金内部分类（计算表）

**规划中**

- [ ] `scripts/deploy_tables.sh` — 批量建表
- [ ] `scripts/generate_catalog.py` — 数据字典生成（扫描各表 `SPEC.md`）
- [ ] 持续扩充表体系（目标 40+ 张）

---

**维护者**: 季俊晔 
**最后更新**: 2026-02-10
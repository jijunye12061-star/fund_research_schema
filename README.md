# 基金研究数据库项目规范文档

## 一、项目概述

### 目标
建立规范化的基金研究数据库（Doris），包含：
- **同步表**：从 Oracle TYTFUND 映射的原始数据表
- **计算表**：基于原始数据计算的衍生指标表

### 特点
- 表结构在本项目定义和管理
- 数据更新通过定时平台（如 DolphinScheduler）调度
- 支持历史补数和增量更新
- 混合数据源（Oracle + Doris 表互相引用）

---

## 二、项目结构

```
fund_research_db/
├── config/
│   ├── database.yaml          # 数据库连接配置
│   └── __init__.py
│
├── utils/
│   ├── db_connector.py        # 数据库连接封装
│   ├── common.py              # 公共函数（交易日历、基金列表等）
│   └── __init__.py
│
├── tables/                     # 所有表统一管理
│   ├── tb_fd_basic_info/
│   │   ├── schema.sql         # 建表语句
│   │   ├── insert.py          # 数据插入逻辑（计算表有此文件）
│   │   ├── view.sql           # 视图映射（同步表有此文件）
│   │   └── README.md          # 表说明文档
│   │
│   ├── tb_fd_perform_abs/
│   │   ├── schema.sql
│   │   ├── insert.py
│   │   └── README.md
│   │
│   ├── tb_fd_portfolio_bd/     # 同步表示例
│   │   ├── schema.sql
│   │   ├── view.sql
│   │   └── README.md
│   └── ...
│
├── scripts/
│   ├── deploy_tables.sh       # 批量执行建表语句
│   └── generate_catalog.py   # 生成数据字典汇总
│
├── docs/
│   ├── PROJECT.md             # 本文档
│   ├── NAMING.md              # 命名规范详细说明
│   ├── TEMPLATE_SYNC.md       # 同步表模板
│   └── TEMPLATE_CALC.md       # 计算表模板
│
└── README.md                  # 项目入口说明
```

---

## 三、文件职责说明

### 3.1 config/database.yaml
**职责**：存储所有数据库连接信息

**内容结构**：
```yaml
dev:  # 开发环境
  oracle:
    host: backup.tytdb.db
    port: 10086
    service_name: tytdb
    username: RDREADER
    password: xxx
  
  doris:
    host: 10.189.18.47
    port: 10096
    database: tytdata
    username: irdev
    password: xxx

prod:  # 生产环境（可选）
  oracle: ...
  doris: ...
```

### 3.2 utils/db_connector.py
**职责**：封装数据库连接逻辑

**需要实现的类**：
1. `OracleConnector` - Oracle 查询连接器
   - 上下文管理器模式
   - 提供 `query(sql, **params)` 方法
   - 支持参数化查询（如 report_dts 列表）
   
2. `DorisConnector` - Doris 连接器
   - 上下文管理器模式
   - 提供 `query(sql)` 方法（用于查询已有表）
   - 提供 `insert(table, df)` 方法（批量写入）
   - 提供 `execute(sql)` 方法（执行 DDL）

**关键设计**：
- 使用 `ConfigLoader` 加载 yaml 配置
- 连接在 `__enter__` 建立，`__exit__` 关闭
- 无需维护长连接，避免超时问题

### 3.3 utils/common.py
**职责**：存放跨表复用的公共函数

**典型函数**：
- `get_trade_calendar(start_date, end_date)` - 获取交易日历
- `get_active_funds(as_of_date)` - 获取存续基金列表
- `get_fund_nav(fund_codes, start_date, end_date)` - 获取基金净值
- 其他业务无关的工具函数

**使用方式**：
```python
from utils.common import get_trade_calendar
from utils.db_connector import OracleConnector, DorisConnector
```

### 3.4 tables/{表名}/schema.sql
**职责**：Doris 建表语句

**内容要求**：
- 完整的 `CREATE TABLE` 语句
- 包含所有字段的 COMMENT
- 定义 UNIQUE KEY 或 DUPLICATE KEY
- 指定分桶策略（DISTRIBUTED BY HASH）

**示例框架**：
```sql
CREATE TABLE tb_fd_perform_abs (
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_trade_date DATE COMMENT '交易日期',
    ...
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_fd_code, c_trade_date, c_period_code)
COMMENT '基金绝对收益指标表'
DISTRIBUTED BY HASH(c_fd_code)
PROPERTIES (...);
```

### 3.5 tables/{表名}/view.sql（仅同步表）
**职责**：Oracle 到 Doris 的视图映射语句

**内容要求**：
- `CREATE VIEW` 语句
- 字段映射关系清晰
- 包含 `WHERE EISDEL = '0'` 等过滤条件
- 字段别名使用 `c_` 前缀

**示例框架**：
```sql
CREATE VIEW tytdata.tb_fd_portfolio_bd AS 
SELECT
    FUNDCODE as c_fd_code,
    ENDDATE as c_report_date,
    ...
FROM TYTFUND.FUND_IV_BONDINVESTO
WHERE EISDEL = '0';
```

### 3.6 tables/{表名}/insert.py（仅计算表）
**职责**：数据计算和插入逻辑

**必须实现的函数**：
```python
def run(calc_date: str):
    """
    主入口函数，由定时任务调用
    
    Args:
        calc_date: 计算日期 'YYYY-MM-DD'
    """
    # 1. 数据准备
    # 2. 批量计算
    # 3. 写入 Doris
```

**代码结构建议**：
```python
# 配置部分（常量、dataclass）
BATCH_SIZE = 100
RF_RATE = 0.02

# 数据获取函数
def _get_source_data(...):
    pass

# 计算逻辑函数
def _calculate_metrics(...):
    pass

# 批处理函数
def _process_batch(...):
    pass

# 主入口
def run(calc_date: str):
    # 调用上述函数完成流程
    pass

# 调试入口
if __name__ == '__main__':
    run('2024-11-27')
```

### 3.7 tables/{表名}/README.md
**职责**：表的完整说明文档

**内容结构**：
```markdown
# tb_xxx - 表中文名称

## 基本信息
- 主键
- 更新频率
- 数据来源（Oracle/Doris/混合）

## 字段清单
（字段表格）

## 枚举值
（如果有）

## 指标说明
（计算表需要详细说明计算逻辑）

## 使用示例
（SQL 查询示例）

## 注意事项
（NULL 处理、数值单位、特殊约定）
```

### 3.8 scripts/deploy_tables.sh
**职责**：批量执行所有表的建表语句

**功能**：
- 遍历 `tables/*/schema.sql`
- 按顺序执行（可考虑依赖关系）
- 错误处理和日志记录

### 3.9 scripts/generate_catalog.py
**职责**：自动生成数据字典文档

**功能**：
- 扫描所有 `tables/*/README.md`
- 汇总成 `docs/DATA_CATALOG.md`
- 按业务模块分类（基金、股票、指数等）

---

## 四、命名规范

### 表命名
**格式**：`tb_{业务模块}_{实体名称}[_{时间维度}][_{区别标识}]`

**示例**：
- `tb_fd_basic_info` - 基金基本信息
- `tb_fd_perform_abs` - 基金绝对收益指标
- `tb_fd_portfolio_stk` - 基金股票持仓

### 字段命名
**通用字段**：
- `c_id` - 主键
- `c_trade_date` - 交易日
- `c_report_date` - 报告期
- `c_updatetime` - 更新时间

**业务字段**：
- `c_fd_code` - 基金代码
- `c_stk_code` - 股票代码
- `c_idx_code` - 指数代码
- `c_{属性}_name` - 名称类
- `c_{属性}_ratio` - 比例类

### 数据类型规范
- 代码：`VARCHAR(20)`
- 日期：`DATE`
- 百分比：`DECIMAL(10,4)` - 存储为百分数（25.5 表示 25.5%）
- 比率：`DECIMAL(15,4)` - 夏普比率等
- 金额：`DECIMAL(20,4)` - 单位元

---

## 五、数据库连接模式

### 使用方式
```python
from utils.db_connector import OracleConnector, DorisConnector

# Oracle 查询
with OracleConnector() as oracle:
    df = oracle.query(sql, report_dts=date_list)

# Doris 查询（混合数据源场景）
with DorisConnector() as doris:
    df = doris.query(sql)

# Doris 写入
with DorisConnector() as doris:
    doris.insert('tb_fd_perform_abs', result_df)
```

### 关键特性
- **上下文管理器**：自动关闭连接，异常安全
- **参数化查询**：Oracle 支持 `**params` 传递日期列表等
- **批量写入**：Doris 的 `insert` 方法自动分块写入

---

## 六、新表添加流程

### 6.1 同步表（从 Oracle 映射）
1. **创建目录**：`tables/tb_new_table/`
2. **编写文件**：
   - `schema.sql` - 复制建表模板，修改字段
   - `view.sql` - 根据 Oracle 表结构生成映射
   - `README.md` - 填写字段说明和枚举值
3. **提交给 DBA**：将 `view.sql` 交给数据库团队执行

### 6.2 计算表（Python 计算）
1. **创建目录**：`tables/tb_new_table/`
2. **编写文件**：
   - `schema.sql` - 定义表结构
   - `insert.py` - 实现 `run(calc_date)` 函数
   - `README.md` - 增加指标说明和注意事项
3. **本地测试**：
   ```python
   from tables.tb_new_table.insert import run
   run('2024-11-27')
   ```
4. **配置定时任务**：在调度平台添加任务，调用 `run` 函数

---

## 七、代码开发规范

### 7.1 核心原则
1. **极致简洁**：单个函数 ≤30 行，超过则拆分
2. **单一职责**：每个函数只做一件事
3. **逻辑分层**：数据获取 → 计算 → 写入，各层解耦
4. **避免过度防御**：研究环境无需过多 try-except

### 7.2 Pythonic 风格
- 优先使用列表推导式和生成器
- pandas 向量化操作，避免显式循环
- 使用 `@dataclass` 定义配置类
- 类型提示增强可读性

### 7.3 典型模式
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class PeriodConfig:
    """配置类示例"""
    code: str
    name: str
    months: Optional[int] = None

def run(calc_date: str):
    """主入口"""
    # 1. 准备数据
    base_data = _get_base_data(calc_date)
    
    # 2. 批处理
    results = []
    for batch in _split_batches(base_data):
        batch_result = _process_batch(batch)
        results.append(batch_result)
    
    # 3. 写入
    final_df = pd.concat(results)
    with DorisConnector() as doris:
        doris.insert('table_name', final_df)
```

---

## 八、提示词使用指南

### 8.1 新建同步表
```
我需要从 Oracle 的 TYTFUND.XXX 表同步数据到 Doris。

原表信息：
- 表名：FUND_YYY
- 字段：FUNDCODE, ENDDATE, VALUE1, VALUE2...

请生成：
1. schema.sql - Doris 建表语句
2. view.sql - 视图映射语句
3. README.md - 表说明文档

参考项目文档：[粘贴本文档]
参考示例：[粘贴 tb_fd_portfolio_bd 示例]
```

### 8.2 新建计算表
```
我需要创建一个计算表 tb_fd_xxx，计算逻辑如下：
[描述业务逻辑]

数据来源：
- Oracle: TYTFUND.AAA 表
- Doris: tb_bbb 表

请生成：
1. schema.sql - 建表语句（字段：xxx, yyy, zzz）
2. insert.py - 计算代码框架
3. README.md - 完整文档

参考项目文档：[粘贴本文档]
参考示例：[粘贴 tb_fd_perform_abs]
```

### 8.3 优化现有代码
```
优化以下代码，要求：
- 拆分过长函数
- 提取公共逻辑到 utils/common.py
- 使用 pandas 向量化替代循环

代码规范：[粘贴第七章]
代码：[粘贴代码]
```

---

## 九、常见问题

### Q1: 同步表和计算表如何区分？
**A**: 看是否需要 Python 代码：
- 同步表：直接从 Oracle 映射，只需 SQL
- 计算表：需要 Python 计算逻辑

### Q2: 混合数据源如何处理？
**A**: 在 `insert.py` 中分别查询：
```python
with OracleConnector() as oracle:
    df1 = oracle.query(sql1)

with DorisConnector() as doris:
    df2 = doris.query(sql2)

result = pd.merge(df1, df2, ...)
```

### Q3: 全量更新和增量更新如何实现？
**A**: 在 `run()` 函数中判断：
```python
def run(calc_date: str, is_full: bool = False):
    if is_full:
        start_date = '1991-01-01'
    else:
        start_date = calc_date
    # 后续逻辑
```

### Q4: 如何补历史数据？
**A**: 循环调用 `run()` 函数：
```python
from datetime import timedelta
import pandas as pd

dates = pd.date_range('2020-01-01', '2024-11-27', freq='D')
for date in dates:
    run(date.strftime('%Y-%m-%d'))
```

---

## 十、后续规划

### 短期（1-2周）
- [ ] 完成 `utils/db_connector.py` 核心代码
- [ ] 完成 `utils/common.py` 基础函数
- [ ] 规范化现有 4-5 张表
- [ ] 编写同步表和计算表模板

### 中期（1个月）
- [ ] 完善文档模板
- [ ] 实现 `scripts/generate_catalog.py`
- [ ] 添加 10+ 新表

### 长期（3个月+）
- [ ] 建立完整的 40+ 表体系
- [ ] 自动化测试框架
- [ ] 数据质量监控

---

**文档版本**: v1.0  
**最后更新**: 2026-02-04  
**维护者**: Jijunye
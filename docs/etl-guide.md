# ETL 与基础设施指南

> 数据库连接、数据同步、调度相关的技术规范。

## 数据库连接架构

| 环境            | 用途          | 地址                      | 协议                  |
|---------------|-------------|-------------------------|---------------------|
| dev (query)   | 查询/DDL      | 10.189.18.47:10096      | MySQL (pymysql)     |
| prod (query)  | 查询/DDL      | master.jgdoris.db:10096 | MySQL (pymysql, F5) |
| prod (insert) | Stream Load | 10.189.23.228:8030      | HTTP                |

**两套协议分工**：MySQL 协议（9030/10096）用于读取和 DDL；HTTP Stream Load（8030）用于写入。F5 负载均衡仅映射了 MySQL 端口，Stream
Load 需直连 FE 节点。

## db_connector.py 核心组件

### OracleConnector

```python
with OracleConnector(env='dev') as oracle:
    df = oracle.query(sql, param1='value')
    df = oracle.query_batch(sql, code_list=fund_codes, batch_size=450)
```

关键点：

- 上下文管理器自动管理连接生命周期
- `query_batch()` 处理大 IN 子句，自动分批（默认 450/批）
- LOB 字段（CLOB/NCLOB）需在连接关闭前读取，按类型检测而非逐字段检查
- `cursor.arraysize = 10000` 提升批量读取性能

### DorisConnector

```python
with DorisConnector(env='dev') as doris:
    df = doris.query(sql)
    doris.insert('table_name', df, batch_size=50000)
    df = doris.query_batch(sql, code_list=codes, start_date='2024-01-01')
```

关键点：

- 查询走 SQLAlchemy + pymysql
- 插入走 HTTP Stream Load（JSON 格式，50k 行/批）
- `query_batch()` 支持额外绑定变量通过 `**kwargs` 传入

## Stream Load 细节

```
代码 → FE节点(8030) → 307重定向 → BE节点 → 写入
```

- 格式：JSON（已移除 CSV 支持）
- `strip_outer_array: true`，`strict_mode: true`
- 307 重定向需手动处理（`allow_redirects=False`）
- 失败直接抛 `RuntimeError`（研究环境直接报错原则）

## 配置管理

`config/database.yaml` 结构：

```yaml
dev:
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

prod:
  oracle: ...
  doris: ...
```

- `ConfigLoader` 单例模式，支持从 `__file__` 向上查找或环境变量覆盖
- 环境切换：每个 insert.py 顶部 `ENV = 'dev'` 常量

## DolphinScheduler (DS) 集成

### DS 资源目录结构

```
jjy/
├── utils/                # 与本地项目完全一致
│   ├── __init__.py
│   ├── db_connector.py
│   ├── common.py
│   └── config/
│       └── database.yaml
├── src/                  # 各表的 insert.py（扁平化）
│   ├── tb_fd_basic_info.py
│   ├── tb_fd_perform_abs.py
│   └── ...
```

### 日期参数

- DS 传入格式：`%Y%m%d`（如 `20260106`）
- 脚本内部统一使用：`%Y-%m-%d`
- 在 `__main__` 入口处转换：

```python
if __name__ == '__main__':
    biz_date = sys.argv[1] if len(sys.argv) > 1 else '20260106'
    biz_date = parse_biz_date(biz_date)  # → 'YYYY-MM-DD'
    run(biz_date)
```

## 新表数据验证工作流

新 insert.py 上线前，按以下步骤验证，**不跳过任何一步**。

### 步骤一：代码审查（开发自查）

- SQL 过滤条件是否正确（参考 database-conventions.md "Oracle 源表业务规则"章节）
- 聚合/差分逻辑有无笛卡尔积风险（多条同 key 记录要先 groupby SUM）
- NULL 是否 fillna（单边缺失 vs 真实 NaN 的业务含义区分）
- 极端分母处理（= 0 或 < 阈值时置 None）

### 步骤二：抽样手算（运行前）

从源表取 1-2 个基金的真实数据，按计算公式手算，与 insert.py 的逻辑对齐：

```bash
# 拉 Oracle 源数据
curl -X POST .../ty/sql -d '{"sql": "...", "db": "oracle"}'
# 拉 Doris 分母/参考数据
curl -X POST .../ty/sql -d '{"sql": "..."}'
```

### 步骤三：运行测试期（2期）

运行最近两个完整报告期，记录条数和日志中的 warning。

### 步骤四：输出数据检查

```sql
-- 分布统计
SELECT COUNT(*), COUNT(target_col), 
       SUM(CASE WHEN target_col < 0 THEN 1 ELSE 0 END) as neg_cnt,
       MIN(target_col), MAX(target_col),
       AVG(target_col),
       PERCENTILE_APPROX(target_col, 0.5) as median,
       PERCENTILE_APPROX(target_col, 0.9) as p90
FROM tytdata.tb_xxx WHERE c_report_date = '...'
```

关注：
- **NULL 率**：> 10% 需解释（是源数据还是业务规则）
- **负值**：数值型指标出现负值必须追查根因
- **精度截断**：出现大量等于 DECIMAL 上限的值说明字段精度不足
- **极端值**：p99 / max 是否合理，结合业务判断（如量化基金换手率高属正常）

### 步骤五：对照验算

取步骤四发现的典型基金（正常值 + 异常值各 1 个），从源表重新手算核对。

---

## 数据同步策略

### 优先使用 Doris

- 衍生表计算优先从 Doris 取数据源（OLAP 查询更快，不影响 Oracle 生产库）
- 频繁使用的 Oracle 表应同步到 Doris
- 小表、低频字典表可直接 Oracle 查

### 并发注意事项

- Doris 并发写 + 读可能 OOM，回填期间串行处理
- 回填时使用动态时间过滤（批次中最早基金成立日），而非固定回看窗口

### 权限约束

- `irdev` 用户仅有 DML（SELECT/INSERT）权限
- DDL（CREATE/DROP/ALTER）需提交给 DBA 执行
- 建表语句写好后交 DBA，日常同步脚本用 `irdev`

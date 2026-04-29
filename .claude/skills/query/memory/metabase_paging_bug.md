---
name: MetabaseConnector 分页丢失 ORDER BY 导致重复行
description: 大于 2000 行的查询，MetabaseConnector 跨页分页不稳定，会拉到大量重复行；超过 2000 行换 DorisConnector
type: feedback
---

# 现象

MetabaseConnector 单次返回上限 2000 行，超过会自动分页。`_fetch_page` 按 db_id 分方言：

- Doris：`SELECT * FROM ({sql}) _t LIMIT {page} OFFSET {offset}`
- Oracle 11g：`SELECT * FROM (SELECT t_.*, ROWNUM MB_RN_ FROM ({sql}) t_ WHERE ROWNUM <= ...) WHERE MB_RN_ > ...`

**两种写法都靠外层包装，会把内层 SQL 的 `ORDER BY` 弄丢**。
- Doris 是 MPP 分布式查询，无序时 LIMIT/OFFSET 不稳定
- Oracle ROWNUM 是查询执行中动态分配的伪列，对无序结果集同样不稳定

结果都是跨页取到的行集合不互斥——大量重复行。

# 实测案例

3878 行的查询（精确 COUNT 验证），分页后：
- 第 1 页 2000 行
- 第 2 页 1878 行
- 总返回 3878 行 ← 行数对得上
- DISTINCT 后只有 2273 行 ← 1605 行重复
- 经理总数 1323，但精确 COUNT 是 1704（少 381 经理）

# 修复

**> 2000 行的查询绝不要用 MetabaseConnector**。换 DorisConnector：

```python
from utils.db_connector import DorisConnector
with DorisConnector('dev') as doris:
    df = doris.query(sql, **params)
```

DorisConnector 用 `pd.read_sql` 单次读取，不分页。

# 何时仍可用 MetabaseConnector

- 在 SQL 层就聚合到 ≤ 2000 行（GROUP BY、COUNT、TOP 类）
- 已知结果行数小（探查、字段确认、单基金查询）

# 触发场景

- 鲜明度核心 SQL（manager × fund × tag 表拉数）
- 全市场分布统计（需要全量经理-基金对应记录）
- 任何"经理 × 基金"行级数据，因为基金经理任职数据动辄 3000+ 行

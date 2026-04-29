# 诊断 ETL 问题用 Metabase 自查，不要让用户跑 debug 脚本

ETL 出问题时（行数对不上、字段错配、上下游数据丢失），优先用 Metabase 接口
（`from utils.metabase import MetabaseConnector`）跑 SQL 自己复现各阶段的过滤
逻辑、对比 Doris/Oracle 端实际数据，**不要让用户**在生产环境写 debug 脚本/加 print。

各 ETL 阶段都能用 SQL 模拟：
- Oracle 拉取 → `MetabaseConnector(DB_ORACLE)` 跑相同 WHERE
- inner join → `IN (:code_list)` + `query_batch` 反查命中率
- VWAP 取数 → 按 sell_date 分组测每只股票

只有当问题确实需要 Python 中间状态（如 pandas merge_asof 行为）时才让用户跑诊断脚本。

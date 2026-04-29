# Query Skill 记忆索引

> 本文件是取数工作流的经验索引。每次取数完成后，如有非显而易见的业务发现，
> 在此添加一行指针并在对应文件中记录详情。
>
> 格式：`- [标题](文件名.md) — 一句话摘要（相关表）`

<!-- 记忆条目从这里开始 -->
- [tb_idx_weight 指数成分权重](tb_idx_weight.md) — c_idx_code 有变体必须用 c_idx_inner_code 定位；部分指数权重仅月末披露
- [tb_fd_dividend_label 基金红利标签](tb_fd_dividend_label.md) — 项目未定义但库里有，含 `高/中高/中股息` 和板块归类标签
- [MetabaseConnector 分页 bug](metabase_paging_bug.md) — > 2000 行查询会因外层 LIMIT/OFFSET 丢失 ORDER BY 而重复抓行；用 DorisConnector 替代
- [tb_fd_asset_allocation 净资产字段](tb_fd_asset_allocation.md) — 净资产列叫 c_fund_nav_total（不是 c_net_asset）；同期多 c_style 行值相同
- [CPI_ISSUEBASICINFO.FINATYPE 取值含义](cpi_finatype.md) — '001'=沪深科创创业, '002'=北交所(及个别异常); 北交所公募参与<2%
- [Doris JOIN ON DATE 列引用等值丢行](doris_join_date_column_eq_bug.md) — JOIN ON `a.c_report_date = b.c_report_date` 会大量丢行（1528→505）；改成常量/绑定变量 `a.c_report_date = :rpt` 即可

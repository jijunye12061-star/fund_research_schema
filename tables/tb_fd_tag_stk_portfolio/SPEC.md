# tb_fd_tag_stk_portfolio — 基金股票投资组合特征标签表

## 概述

基金画像标签体系第三张表，覆盖**组合构建（集中度）、主动管理、交易特征**三大维度。

- **KEY**: `(c_report_date, c_fd_code)`
- **计算频率**: 季度末，DS 调度
- **基金范围**: 主动权益（001001）+ 全部混合型（004），仅主代码（去重A/C子份额和联接基金）
- **阈值机制**: 相对阈值均按基金类型（001/002/003/004）分别排名
- **依赖表**: `tb_fd_ind_weight` / `tb_fd_portfolio_stk` / `tb_idx_weight` / `tb_stk_industry` / `tb_fd_category` / `tb_trade_calendar`

---

## 字段说明

### 组合构建（集中度）

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_sector_hhi` | DECIMAL | 板块HHI：六大板块权重归一化后平方和（0~1），近**4期半年报**均值 |
| `c_ind_hhi` | DECIMAL | 行业HHI：中信一级行业权重平方和/总权重²（0~1），近**4期半年报**均值 |
| `c_ind_top5_ratio` | DECIMAL | 前5大行业权重占比（%），近**4期半年报**均值 |
| `c_ind_concent_rank` | DECIMAL | 行业集中度复合排名：(HHI分位排名 + top5分位排名) / 2，按基金类型，0~1 |
| `c_top10_ratio` | DECIMAL | 前10大持股**占股票仓位**比例（小数），近**8期季报**均值；= top10占NAV(%) / 股票仓位(%)，归一化消除仓位高低影响 |
| `c_sector_concent_tag` | VARCHAR | 板块集中度：**集中** / **均衡** / **分散**（c_sector_hhi的70%/30%分位，按类型） |
| `c_ind_concent_tag` | VARCHAR | 行业集中度：**集中** / **均衡** / **分散**（c_ind_concent_rank的70%/30%分位，按类型） |
| `c_stk_concent_tag` | VARCHAR | 个股集中度：**集中** / **均衡** / **分散**（c_top10_ratio的70%/30%分位，按类型） |

### 主动管理

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_active_sector` | DECIMAL | 主动板块偏离度（%）：基金各板块权重与中证800板块权重绝对差均值，近4期均值 |
| `c_active_ind` | DECIMAL | 主动行业偏离度（%）：板块内部行业偏离均值按板块权重加权，近4期均值 |
| `c_active_sector_rank` | DECIMAL | 主动板块偏离百分比排名（按基金类型，0~1） |
| `c_active_ind_rank` | DECIMAL | 主动行业偏离百分比排名（按基金类型，0~1） |
| `c_active_tag` | VARCHAR | **主动配置**（两者均≥70%）/ **主动板块配置** / **主动行业配置** / 空 |
| `c_new_stk_ratio` | DECIMAL | 持股扩新（%）：T期全持仓中未出现在T-1~T-3期的合计权重；季报期前向填充最近半年报期值 |
| `c_new_stk_tag` | VARCHAR | **积极**（≥50%）/ **适中**（≥20%）/ **保守**（<20%）；季报期前向填充 |
| `c_crowd_score` | DECIMAL | 全市场抱团度：基金持仓加权的 tb_stk_crowding_score.c_crowd_score_mkt 均值；仅半年报期有值，季报期前向填充 |
| `c_crowd_internal_score` | DECIMAL | 同公司抱团度：公司内股票持仓市值百分位排名的加权均值；仅半年报期有值，季报期前向填充 |
| `c_crowd_tag` | VARCHAR | 抱团度标签：**高抱团** / **中抱团** / **低抱团**（全市场+同公司排名等权复合，按基金类型70%/30%分位） |

### 交易特征

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_turnover_avg` | DECIMAL | 换手率均值（倍）：近4期半年报的 tb_fd_turnover.c_turnover_rate 均值除以100；季报期前向填充 |
| `c_turnover_tag` | VARCHAR | 换手率标签：**高换手** / **中换手** / **低换手**（按基金类型70%/30%分位） |
| `c_heavy_retain_rate` | DECIMAL | 重仓股留存率均值（%）：T-1期重仓在T期保留数量/T-1期重仓数量，近8期均值 |
| `c_heavy_turnover` | DECIMAL | 重仓股换手率均值（%）：1 - T-1期留存重仓权重/T-1期总权重，近8期均值 |
| `c_heavy_hold_period` | DECIMAL | 重仓股持有期均值（期数）：当前重仓股各自连续出现在重仓列表的期数均值 |
| `c_heavy_trade_rank` | DECIMAL | 重仓交易复合排名（按基金类型，0~1）：留存率升序 + 换手率**降序** + 持有期升序，等权 |
| `c_heavy_trade_tag` | VARCHAR | **偏长期持有** / **持有期适中** / **偏短期交易**（c_heavy_trade_rank的70%/30%分位，按类型） |

---

## 注意事项

每个报告期触发**两次**：季报截止日（约报告期末 +15 工作日）和半年报/年报截止日（约 +60/90 自然日）。两次写同一 `c_report_date`，UNIQUE KEY 覆盖。查数时需注意字段更新频率：

### 字段更新频率

| 类型 | 字段 | 季报期行为 |
|---|---|---|
| 季报级（每季更新） | `c_top10_ratio`、重仓交易系列（7个） | 每次都重算 |
| 半年报级（自动前向填充） | 集中度、主动偏离、换手率、抱团度、买卖时机（19个） | 回退到最近半年报期，值不变 |
| 半年报级（数据驱动填充） | `c_new_stk_ratio`、`c_new_stk_tag` | 中报/年报未出时回退上一期，出后覆盖 |

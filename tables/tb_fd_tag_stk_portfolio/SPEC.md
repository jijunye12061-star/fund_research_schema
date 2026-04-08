# tb_fd_tag_stk_portfolio — 基金股票投资组合特征标签表

## 概述

基金画像标签体系第三张表，覆盖**组合构建（集中度）、主动管理、交易特征**三大维度。

- **KEY**: `(c_report_date, c_fd_code)`
- **计算频率**: 季度末，DS 调度
- **基金范围**: 主动权益（001001）+ 全部混合型（004），仅主代码（去重A/C子份额和联接基金）
- **阈值机制**: 相对阈值均按基金类型（001/002/003/004）分别排名

---

## 数据依赖

| 上游 | 用途 |
|---|---|
| `tb_fd_ind_weight` | 行业权重（仅半年报期：06-30/12-31） |
| `tb_fd_portfolio_stk` | 季报重仓股（c_style: 01/03/05/06）；半年报全持仓（02/04） |
| `tb_idx_weight` | 中证800成分股日权重（c_idx_code='000906'） |
| `tb_stk_industry` | 个股→中信一级行业（c_citic_code前6位） |
| `tb_fd_category` | 基金类型（c_type1_code） |
| `tb_trade_calendar` | 报告期→最近交易日 |
| `sector_mapping.yaml` | 中信一级行业→六大板块映射（复用 region_sector 目录） |

---

## 字段说明

### 组合构建（集中度）

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_sector_hhi` | DECIMAL | 板块HHI：六大板块权重归一化后平方和（0~1），近**4期半年报**均值 |
| `c_ind_hhi` | DECIMAL | 行业HHI：中信一级行业权重平方和/总权重²（0~1），近**4期半年报**均值 |
| `c_ind_top5_ratio` | DECIMAL | 前5大行业权重占比（%），近**4期半年报**均值 |
| `c_ind_concent_rank` | DECIMAL | 行业集中度复合排名：(HHI分位排名 + top5分位排名) / 2，按基金类型，0~1 |
| `c_top10_ratio` | DECIMAL | 前10大持股权重占比（%），近**8期季报**均值（季报有重仓股数据） |
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
| `c_new_stk_ratio` | DECIMAL | 持股扩新（%）：T期全持仓中未出现在T-1~T-3期的合计权重；季报期为NULL |
| `c_new_stk_tag` | VARCHAR | **积极**（≥50%）/ **适中**（≥20%）/ **保守**（<20%）；季报期为NULL |
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

## 关键计算说明

### 行业偏离度（主动行业配置）算法

主动行业偏离是**板块内部**衡量，避免简单行业偏离被板块集中度放大：

1. 对每个板块 S，将基金和基准在板块内的行业权重各自归一化（板块内合计=100%）
2. 计算板块内各行业权重差的绝对值均值 → 该板块的行业偏离
3. 以基金的板块权重为权重，加权汇总所有板块的行业偏离

### 重仓交易复合排名方向

三个指标方向一致（值越大代表越偏长期持有）：
- `c_heavy_retain_rate`：升序排名（留存率高 = 偏长期）
- `c_heavy_turnover`：**降序**排名（换手率低 = 偏长期）
- `c_heavy_hold_period`：升序排名（持有期长 = 偏长期）

---

## 延后实现事项

- [x] `c_turnover_avg` / `c_turnover_tag`：已建 `tb_fd_turnover` 表（Oracle FUND_IV_STOCKTRADESUM → Doris）
- [x] `c_crowd_score` / `c_crowd_internal_score` / `c_crowd_tag`：已建 `tb_stk_crowding_score` 个股抱团度中间表
- [ ] 买入/卖出时点标签（左侧/右侧）：需要个股区间收益数据
- [ ] 回溯修改 `tb_fd_tag_stk_style`：相对标签改为按基金类型分别排名（当前为全市场统一）

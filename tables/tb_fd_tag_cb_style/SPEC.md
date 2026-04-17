# tb_fd_tag_cb_style — 固收+基金转债投资风格标签表

## 基本信息

- **主键**: (c_report_date, c_fd_code)
- **表类型**: 计算型（insert.py 季度调度）
- **更新频率**: 季度（调度时机同 `tb_fd_tag_bd_style`）
- **基金范围**: `tb_fd_category` 固收+（002）主代码，近8期 `c_bd_convertible_ratio` 均值 ≥ 1%
- **历史起点**: 2016-12-31
- **依赖表**: `tb_fd_portfolio_bd` / `tb_bd_basic_info` / `tb_stk_industry` / `tb_cb_analysis` / `tb_stk_risk_factor` / `tb_stk_barra_status` / `tb_fd_asset_allocation` / `tb_fd_category` / Oracle `BOND_CB_SWAPDETAIL`

## 字段清单

### 主键与控制字段

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_report_date | DATE | 报告日期（季度末） |
| c_fd_code | VARCHAR(20) | 基金代码（主代码） |
| c_updatetime | DATETIME(6) | 更新时间 |

### 组合构建（近8期季报均值）

CB持仓权重基于 `c_nav_ratio`（占净值比），在基金内部归一化后计算集中度。

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_cb_top10_ratio | DECIMAL(10,4) | 前10大转债占CB总仓位比例（%） |
| c_cb_hhi | DECIMAL(10,6) | 个券HHI集中度（0~1），越高越集中 |
| c_cb_concent_tag | VARCHAR(10) | 个券集中度标签，见枚举值 |
| c_cb_ind_top5_ratio | DECIMAL(10,4) | 前5大行业转债占比（%），行业按中信一级 |
| c_cb_ind_hhi | DECIMAL(10,6) | 行业HHI集中度（0~1） |
| c_cb_ind_concent_tag | VARCHAR(10) | 行业集中度标签，见枚举值 |
| c_cb_sector_top1_ratio | DECIMAL(10,4) | 最大板块转债占比（%），六大板块之最大 |
| c_cb_sector_hhi | DECIMAL(10,6) | 板块HHI集中度（0~1） |
| c_cb_sector_concent_score | DECIMAL(10,4) | 板块集中度复合分位（0~1），(top1_rank+hhi_rank)/2 |
| c_cb_sector_concent_tag | VARCHAR(10) | 板块集中度标签，见枚举值 |

### 板块特征与偏好（近8期季报均值）

板块按中信一级行业（025）→ 六大板块映射（同 `tb_fd_tag_stk_region_sector`）。

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_cb_sector_cycle | DECIMAL(10,4) | 周期板块转债权重均值（%） |
| c_cb_sector_mfg | DECIMAL(10,4) | 中游制造板块转债权重均值（%） |
| c_cb_sector_tech | DECIMAL(10,4) | 科技板块转债权重均值（%） |
| c_cb_sector_consumer | DECIMAL(10,4) | 消费板块转债权重均值（%） |
| c_cb_sector_pharma | DECIMAL(10,4) | 医药板块转债权重均值（%） |
| c_cb_sector_fin | DECIMAL(10,4) | 金融地产板块转债权重均值（%） |
| c_cb_sector_chg | DECIMAL(10,4) | 板块权重变动指标（%），各板块绝对变化按板块均值加权 |
| c_cb_sector_tag | VARCHAR(10) | 板块标签，见枚举值 |
| c_cb_sector_pref | VARCHAR(20) | 板块偏好，仅赛道型有值 |

### 交易特征（近8期季报）

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_cb_retain_rate | DECIMAL(10,4) | 转债留存率均值（%），近7期相邻季报均值 |
| c_cb_turnover_rate | DECIMAL(10,4) | 转债换手率均值（%），近7期相邻季报均值 |
| c_cb_hold_period | DECIMAL(10,4) | 转债平均持有期数（期），持续出现在持仓中的期数均值 |
| c_cb_trade_score | DECIMAL(10,4) | 交易特征复合分位（0~1），越高越偏长期持有 |
| c_cb_trade_tag | VARCHAR(20) | 交易标签，见枚举值 |

### 转债风格（近8期季报，分位基于全市场CB）

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_cb_debt_like_ratio | DECIMAL(10,4) | 平底溢价率≤-20%的CB占比（%），各期均值 |
| c_cb_equity_like_ratio | DECIMAL(10,4) | 平底溢价率≥20%的CB占比（%），各期均值 |
| c_cb_attr_tag | VARCHAR(10) | 属性标签，见枚举值 |
| c_cb_equity_score | DECIMAL(10,4) | 转股溢价率全市场分位加权均值（0~1），越低=股性越强 |
| c_cb_equity_tag | VARCHAR(10) | 股性标签，见枚举值 |
| c_cb_bond_score | DECIMAL(10,4) | 纯债溢价率全市场分位加权均值（0~1），越低=债性越强 |
| c_cb_bond_tag | VARCHAR(10) | 债性标签，见枚举值 |
| c_cb_balance_score | DECIMAL(10,4) | 余额全市场分位加权均值（0~1） |
| c_cb_balance_tag | VARCHAR(10) | 余额标签，见枚举值 |

### 正股风格（近8期季报均值）

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_stk_mktcap_score | DECIMAL(10,4) | 正股流通市值全市场分位均值（0~1） |
| c_stk_mktcap_tag | VARCHAR(10) | 市值标签，见枚举值 |
| c_stk_value_score | DECIMAL(10,4) | Barra VALUE因子加权暴露（cb_nav_ratio加权），近8期均值 |
| c_stk_growth_score | DECIMAL(10,4) | Barra GROWTH因子加权暴露，近8期均值 |
| c_stk_profit_score | DECIMAL(10,4) | Barra PROF因子加权暴露，近8期均值 |
| c_stk_style_score | DECIMAL(10,4) | 正股风格复合得分（GROWTH - VALUE），正值偏成长 |
| c_stk_style_tag | VARCHAR(10) | 正股风格标签，见枚举值 |

## 枚举值

### 集中度标签（c_cb_concent_tag / c_cb_ind_concent_tag / c_cb_sector_concent_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 集中 | 复合分位 ≥ 70%（样本内） |
| 均衡 | 30% ≤ 复合分位 < 70% |
| 分散 | 复合分位 < 30% |

### 板块标签（c_cb_sector_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 赛道型 | max(六大板块权重均值) > 50%（且非轮动） |
| 轮动型 | sector_chg ≥ 20% 且 max × (1 − chg/100) ≤ 50% |
| 均衡型 | 其他 |

### 交易标签（c_cb_trade_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 长期持有 | 交易复合分位 ≥ 70% |
| 持有适中 | 30% ≤ 复合分位 < 70% |
| 频繁交易 | 复合分位 < 30% |

### 属性标签（c_cb_attr_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 偏债 | debt_like_ratio > 50% |
| 偏股 | equity_like_ratio > 30%（且不满足偏债） |
| 均衡 | 其他 |

### 股性标签（c_cb_equity_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 股性强 | c_cb_equity_score ≤ 0.30（转股溢价率低，全市场前30%） |
| 股性中等 | 0.30 < score ≤ 0.70 |
| 股性弱 | c_cb_equity_score > 0.70 |

### 债性标签（c_cb_bond_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 债性强 | c_cb_bond_score ≤ 0.30（纯债溢价率低，全市场前30%） |
| 债性中等 | 0.30 < score ≤ 0.70 |
| 债性弱 | c_cb_bond_score > 0.70 |

### 余额标签（c_cb_balance_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 高余额 | c_cb_balance_score ≥ 0.70（余额全市场前30%大） |
| 中余额 | 0.30 ≤ score < 0.70 |
| 低余额 | c_cb_balance_score < 0.30 |

### 市值标签（c_stk_mktcap_tag）

| 取值 | 判断逻辑 |
|------|---------|
| 大盘 | c_stk_mktcap_score ≥ 0.70 |
| 中盘 | 0.30 ≤ score < 0.70 |
| 小盘 | c_stk_mktcap_score < 0.30 |

### 正股风格标签（c_stk_style_tag）

| 取值 | 判断逻辑（基于 c_stk_style_score 在样本内分位） |
|------|---------|
| 成长 | c_stk_style_score ≥ 67th 百分位 |
| 价值 | c_stk_style_score ≤ 33rd 百分位 |
| 均衡 | 其他 |

## 注意事项

- **CB持仓识别**：转股期CB（`c_bd_type='2'`，全量）+ 普通债持仓中通过 `tb_bd_basic_info` 识别的未转股期可转债（`c_bd_type='1'` + `c_bd_type='可转换债券'`）
- **季报全量**：`c_bd_type='2'`（转股期CB）在季报中全量披露，不仅限于前5大
- **分位计算**：equity_score/bond_score/balance_score 的分位基于全市场CB当期截面（PERCENT_RANK），非样本内排名
- **balance 来源**：Oracle `BOND_CB_SWAPDETAIL.UNTRANSFER_AMT`（单位：元），取近交易日截面
- **正股因子**：使用报告期对应最近交易日（`tb_trade_calendar.c_max_trade_date`）的 Barra 因子
- **无正股 CB**：无法映射 c_stk_code 的转债（如可交换债已套利完的）不参与正股风格计算

## 使用示例

```sql
-- 查询某期固收+基金转债风格全貌
SELECT c_fd_code,
       c_cb_attr_tag, c_cb_equity_tag, c_cb_bond_tag, c_cb_balance_tag,
       c_cb_sector_tag, c_cb_sector_pref,
       c_stk_style_tag, c_stk_mktcap_tag
FROM tytdata.tb_fd_tag_cb_style
WHERE c_report_date = '2025-03-31';

-- 筛选偏股型+科技赛道的转债基金
SELECT c_fd_code, c_cb_equity_score, c_cb_sector_tech
FROM tytdata.tb_fd_tag_cb_style
WHERE c_report_date = '2025-03-31'
  AND c_cb_attr_tag = '偏股'
  AND c_cb_sector_tag = '赛道型'
  AND c_cb_sector_pref = '科技'
ORDER BY c_cb_equity_score;

-- 分析转债风格分布（某期截面）
SELECT c_cb_attr_tag, c_stk_style_tag, COUNT(*) AS cnt
FROM tytdata.tb_fd_tag_cb_style
WHERE c_report_date = '2025-03-31'
GROUP BY c_cb_attr_tag, c_stk_style_tag
ORDER BY cnt DESC;
```

# 转债风格标签体系建设计划

> **状态**: 待执行 | **日期**: 2026-04-15 | **负责人**: jijunye  
> ⚠️ 完工后删除此文件

---

## Context

基金画像标签体系已完成股票端（`tb_fd_tag_stk_style` / `tb_fd_tag_stk_portfolio` / `tb_fd_tag_stk_region_sector`）和债券端（`tb_fd_tag_bd_style`），现需新增**转债端标签**，覆盖组合构建、板块特征、交易特征、转债风格、正股风格 5 个维度。

基于 Oracle 数据探查，涉及 4 张未同步到 Doris 的 Oracle 源表。计划拆分为"先逐表同步，再建标签表"的推进方式，每个表单独过一遍。

---

## 数据资产盘点

### 已有（直接可用）

| Doris 表 | 用途 |
|----------|------|
| `tb_fd_portfolio_bd` | 视图，映射 `FUND_IV_BONDINVESTO`（与 `FUND_IV_BONDINVESTD` 数据等价），含转债持仓。`c_bd_type='2'` 为转股期CB，**季报全量披露**（2025-03-31 有 86,002 条，非仅前5大）；`c_bd_type='1'` 中也可能有未进入转股期的CB，需 JOIN `tb_bd_basic_info` 识别 |
| `tb_stk_industry` | 申万行业归属（计算表，日频），用于 cb→stk→行业/板块映射 |
| `tb_dict_params` | 行业/概念分类代码字典 |
| `tb_fd_category` | 基金分类，过滤固收+（002） |
| `tb_fd_asset_allocation` | 资产配置，含 `c_bd_convertible_ratio`（可转债占比），用于样本池过滤（近8期均值≥1%） |
| `tb_stk_risk_factor` / `tb_stk_barra_status` | Barra 风险因子，用于正股风格维度 |
| `tb_stk_quote_daily` | A股行情，用于正股流通市值 |

### 需新建（Oracle 源表同步）

| Oracle 源表 | 拟建 Doris 表 | 类型 | 数据量 | 说明 |
|-------------|-------------|------|--------|------|
| `BOND_BA_INFO` | `tb_bd_basic_info` | 视图 | ~59 万（全量债券） | 债券基础信息，含 `SWAPSCODE`（正股代码）、`BONDTYPE`、`LISTDATE`、`DELISTDATE`、`ISSUEVOL` 等 |
| `BOND_DR_CBANALYSIS` | `tb_cb_analysis` | 视图 | ~28 万/年（日频） | 转债估值指标：转股溢价率、纯债溢价率、平底溢价率、纯债价值、转换价值 |
| `BOND_TD_DAILY` | `tb_bd_quote_daily` | 视图 | 极大（全债券日频） | 债券行情：净价、全价、成交量、成交额；对标 `tb_stk_quote_daily` |
| `BOND_CB_SWAPDETAIL` | **不单独建表** | — | ~40 万（全量） | 见下方余额评估 |

### 余额评估结论：不单独建表

`BOND_CB_SWAPDETAIL` 的关键字段：`SWAPPRICE`（当日转股价）、`UNTRANSFER_AMT`（未转股余额，**单位：元**）。

- `SWAPPRICE` — 已被 `BOND_DR_CBANALYSIS.SWAPVALUE`（转换价值）间接覆盖
- `UNTRANSFER_AMT` — 仅在标签计算（余额维度）使用，且只需季报期截面（4次/年）
- 在 `tb_fd_tag_cb_style` 的 insert.py 中直接查 Oracle 取报告期余额即可
- 如后续有独立的转股进度分析需求，再补建视图

---

## 任务拆分（逐个推进，Task 1-3 可并行）

```
Task 1: tb_bd_basic_info    (视图)  ← 无依赖
Task 2: tb_cb_analysis      (视图)  ← 无依赖  } 三个视图工作量小，先一口气过完
Task 3: tb_bd_quote_daily   (视图)  ← 无依赖
Task 4: tb_fd_tag_cb_style  (计算表) ← 依赖 Task 1-3 全部完成
```

---

### Task 1: tb_bd_basic_info — 债券基础信息（视图）

**Source**: `TYTFUND.BOND_BA_INFO`，`WHERE EISDEL = '0'`

| Doris 字段 | Oracle 字段 | 说明 |
|-----------|------------|------|
| `c_bd_code` | `BONDCODE` | 债券代码（6位）|
| `c_bd_inner_code` | `SECURITYVARIETYCODE` | 债券内码 |
| `c_bd_name` | `SNAME` | 债券简称 |
| `c_bd_full_name` | `FNAME` | 债券全称 |
| `c_bd_type` | `BONDTYPE` | 债券类型（可转换债券/可交换债券/...，共44种）|
| `c_bd_type_code` | `BONDTYPECODE` | 债券类型代码 |
| `c_stk_code` | `SWAPSCODE` | 正股代码（仅转债类有值，1,629条）|
| `c_issue_date` | `ISSUEDATE` | 发行日 |
| `c_list_date` | `LISTDATE` | 上市日 |
| `c_delist_date` | `DELISTDATE` | 退市日 |
| `c_maturity_date` | `MRTYDATE` | 到期日 |
| `c_issue_vol` | `ISSUEVOL` | 发行规模（**亿元**）|
| `c_par_value` | `PARVALUE` | 面值 |
| `c_coupon_rate` | `COUPONRATE` | 票面利率（%）|
| `c_credit_rating` | `CREDITRATING` | 信用评级 |
| `c_exchange` | `TEXCH` | 交易所 |

**产出**: `tables/tb_bd_basic_info/view.sql` + `SPEC.md`

---

### Task 2: tb_cb_analysis — 转债估值分析（视图）

**Source**: `TYTFUND.BOND_DR_CBANALYSIS`，`WHERE EISDEL = '0'`  
**数据量**: ~28万条/年，日更，最新数据更新至今日  
**注意**: 部分非标准品种的 `PUREBONDVALUE`/`FLOOROR` 可能为 NULL，视图直接传，计算时 JOIN 取有值记录

| Doris 字段 | Oracle 字段 | 说明 |
|-----------|------------|------|
| `c_trade_date` | `TDATE` | 交易日期 |
| `c_bd_code` | `BONDCODE` | 转债代码 |
| `c_bd_inner_code` | `SECURITYVARIETYCODE` | 内码 |
| `c_pure_bond_value` | `PUREBONDVALUE` | 纯债价值（元）|
| `c_conv_value` | `SWAPVALUE` | 转换价值（元）= 正股价 × 100/转股价 |
| `c_conv_prem_rate` | `SWAPOR` | 转股溢价率（%）= (转债价-转换价值)/转换价值 |
| `c_straight_prem_rate` | `PUREBONDOR` | 纯债溢价率（%）= (转债价-纯债价值)/纯债价值 |
| `c_floor_prem_rate` | `FLOOROR` | 平底溢价率（%）= (转换价值-纯债价值)/纯债价值 |
| `c_bond_value` | `BOND_VALUE_CB` | 转债理论价值（含期权价值的综合估值）|
| `c_bond_premium` | `BOND_PREMIUM_CB` | 转债溢价额（转债价-理论价值）|
| `c_bond_prem_rate` | `BOND_PREMRATIO_CB` | 转债溢价率（%）|

**产出**: `tables/tb_cb_analysis/view.sql` + `SPEC.md`

---

### Task 3: tb_bd_quote_daily — 债券行情（视图）

**Source**: `TYTFUND.BOND_TD_DAILY`，`WHERE EISDEL = '0'`  
**注意**: 全债券日频表，数据量极大。查询必须带 `c_bd_code` + `c_trade_date` 条件  
**净价 vs 全价**: 转债通常用全价（FCLOSE）；部分转债 CCLOSE 为 NULL

| Doris 字段 | Oracle 字段 | 说明 |
|-----------|------------|------|
| `c_trade_date` | `TDATE` | 交易日期 |
| `c_bd_code` | `BONDCODE` | 债券代码 |
| `c_bd_inner_code` | `SECURITYVARIETYCODE` | 内码 |
| `c_bd_name` | `SNAME` | 债券简称 |
| `c_net_open` | `COPEN` | 净价开盘 |
| `c_net_close` | `CCLOSE` | 净价收盘（部分转债为 NULL）|
| `c_net_high` | `CHIGH` | 净价最高 |
| `c_net_low` | `CLOW` | 净价最低 |
| `c_net_pre_close` | `LCCLOSE` | 净价昨收 |
| `c_full_open` | `FOPEN` | 全价开盘 |
| `c_full_close` | `FCLOSE` | 全价收盘 |
| `c_full_high` | `FHIGH` | 全价最高 |
| `c_full_low` | `FLOW` | 全价最低 |
| `c_full_pre_close` | `LFCLOSE` | 全价昨收 |
| `c_volume` | `TVOL` | 成交量（张）|
| `c_amount` | `TVAL` | 成交额（元）|
| `c_net_chg_rate` | `CCHGRATE` | 净价涨跌幅（%）|

**产出**: `tables/tb_bd_quote_daily/view.sql` + `SPEC.md`

---

### Task 4: tb_fd_tag_cb_style — 转债风格标签（计算表）

**Type**: 计算表，`should_run(calc_date, ReportFreq.QUARTERLY)`  
**基金范围**: `tb_fd_category` 固收+（002）主代码，近8期 `c_bd_convertible_ratio` 均值 ≥ 1%  
**主键**: `(c_report_date, c_fd_code)` | **历史起点**: 2016-12-31  

#### CB 持仓识别逻辑
```python
# 完整可转债持仓 = 转股期CB（BONDTYPE=2全量）+ 未转股期CB（混在普通债TOP5里）
cb_type2 = portfolio_bd WHERE c_bd_type = '2'  # 转股期可转债，季报全量
cb_type1 = portfolio_bd WHERE c_bd_type = '1'
          AND c_bd_code IN (bd_basic_info WHERE c_bd_type = '可转换债券')  # 过滤出前5大中的CB
cb_all = UNION(cb_type2, cb_type1)
```

#### 5维度字段（共42个）

| 维度 | 字段数 | 关键数据来源 | 计算窗口 |
|------|--------|------------|---------|
| **组合构建**（个券/行业/板块集中度）| 10 | `tb_fd_portfolio_bd` + `tb_bd_basic_info` + `tb_stk_industry` | 近8期季报 |
| **板块特征与偏好** | 9 | 同上（申万→六大板块映射）| 近8期季报 |
| **交易特征**（留存率/换手率/持有期）| 5 | `tb_fd_portfolio_bd` | 近8期季报 |
| **转债风格**（属性/股性/债性/余额）| 11 | `tb_cb_analysis`（分位数）+ Oracle `BOND_CB_SWAPDETAIL`（余额截面）| 近8期季报 |
| **正股风格**（市值/价值/成长/盈利）| 7 | `tb_bd_basic_info.c_stk_code` → `tb_stk_risk_factor` | 近8期季报 |

#### 字段列表（转债风格维度完整版）

| 字段 | 说明 | 标签规则 |
|------|------|---------|
| `c_cb_debt_like_ratio` | 平底溢价率≤-20%占比（%），近8期均值 | — |
| `c_cb_equity_like_ratio` | 平底溢价率≥20%占比（%），近8期均值 | — |
| `c_cb_attr_tag` | 属性标签 | **偏债**（debt_like>50%）/ **偏股**（equity_like>30%）/ **均衡** |
| `c_cb_equity_score` | 转股溢价率全市场分位持仓加权均值（0~1），近8期均值；越低=股性越强 | — |
| `c_cb_equity_tag` | 股性标签 | **股性强**（前30%）/ **股性中等** / **股性弱** |
| `c_cb_bond_score` | 纯债溢价率全市场分位持仓加权均值（0~1），近8期均值；越低=债性越强 | — |
| `c_cb_bond_tag` | 债性标签 | **债性强** / **债性中等** / **债性弱** |
| `c_cb_balance_score` | 余额全市场分位持仓加权均值（0~1），近8期均值 | — |
| `c_cb_balance_tag` | 余额标签 | **高余额** / **中余额** / **低余额** |

> 隐含波动率维度：Oracle 无原始数据（无 IMPVOL 类表），Phase 2 用 BSM 模型计算，当前跳过

**产出**: `tables/tb_fd_tag_cb_style/schema.sql` + `SPEC.md` + `insert.py`

---

## 参考文件

| 文件 | 用途 |
|------|------|
| `tables/tb_fd_portfolio_bd/view.sql` | 视图写法参考 |
| `tables/tb_stk_quote_daily/view.sql` | 行情视图参考 |
| `tables/tb_fd_tag_stk_portfolio/SPEC.md` | 组合构建+交易特征字段参考 |
| `tables/tb_fd_tag_stk_region_sector/SPEC.md` | 板块标签规则参考 |
| `tables/tb_fd_tag_stk_style/SPEC.md` | 正股风格标签规则参考 |
| `scripts/转债投资风格.py` | 现有研究脚本，复用计算逻辑 |
| `scripts/转债交易特征.py` | 现有研究脚本，复用交易指标计算 |
| `docs/infra/view-mapping-guide.md` | 视图映射规范 |
| `docs/infra/database-conventions.md` | DDL 约定 |

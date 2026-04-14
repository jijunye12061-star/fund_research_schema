---
name: 基金数据业务规则
description: 项目中的关键数据规则：基金代码去重、c_style 财报来源、两轮调度节奏、字段选择
type: project
---

## 基金代码去重（必须）

所有涉及基金代码的查询，必须用主代码去重。

- `tb_fd_basic_info.c_init_code`：主代码（A份额 = 主代码；C/B/I/R份额指向A份额；ETF联接基金指向ETF）
- **过滤条件**：`b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL`

---

## c_style 财报来源标识

跨多张表（`tb_fd_portfolio_stk`、`tb_fd_asset_allocation`、`tb_fd_portfolio_bd` 等）通用，用于区分报告来源。

| c_style | 报告类型 | 报告期   | 披露内容                                |
|---------|------|-------|-------------------------------------|
| 01      | 一季报  | 03-31 | 资产配置比例、前十大持股、前五大债券持仓（含转股期可转债）       |
| 03      | 三季报  | 09-30 | 同 01                                |
| 05      | 二季报  | 06-30 | 同 01                                |
| 06      | 四季报  | 12-31 | 同 01                                |
| 02      | 半年报  | 06-30 | 全量股票持仓、全量债券持仓、利率敏感性久期、买卖股票金额（换手率用）等 |
| 04      | 年报   | 12-31 | 同 02                                |

**关键**：06-30/12-31 各有两次披露，时间差 5-6 周（05/06 先到，02/04 后到） 资产配置/前十大持股等信息披露两次。

**各表依赖的 c_style**：

- 需要全持仓（`tb_fd_ind_weight`、`tb_stk_crowding_score`、`tb_fd_tag_stk_portfolio` 持股扩新）：`c_style IN ('02', '04')`
- 需要重仓股 top10：`c_style IN ('01','03','05','06')`
- 查询方式：**必须用 `c_report_date = :date` 逐期查**，禁止 BETWEEN（有非标准报告期数据）

---

## 调度节奏：两轮触发

**第一轮 — 季报披露后（报告期末 +15 工作日，约 4/22、7/22、10/22、次年 1/22）**

可计算的表（仅用季报数据）：

- `tb_fd_category`、`tb_fd_tag_asset`、`tb_fd_tag_stk_region_sector`（板块字段前向填充）、`tb_fd_tag_bd_style`

标签表首次写入（季报级字段正式值，半年报级字段前向填充上期数据）：

- `tb_fd_tag_stk_style`（季报期内部跳过，前向填充）
- `tb_fd_tag_stk_portfolio`（重仓交易/top10 更新，集中度/换手率/抱团度等前向填充）

**第二轮 — 半年报/年报全量披露后（06-30+60天≈8/29，12-31+90天≈次年3/31）**

可计算的表（依赖全持仓数据）：

- `tb_fd_ind_weight`、`tb_fd_turnover`、`tb_fd_bd_risk_metric`（可并行）
- `tb_stk_crowding_score`

标签表覆盖重跑（UNIQUE KEY 覆盖写入，半年报级字段正式计算）：

- `tb_fd_tag_stk_style`、`tb_fd_tag_stk_portfolio`（全字段更新）

---

## tb_fd_category 分类体系

- `c_type1_code`：一级（001权益/002固收加/003债券/004混合/005QDII/006FOF/007另类/008货币）
- `c_type2_code`：二级（如 001001 主动权益、001002 指数增强、001003 被动指数）
- 002/004 中都有"偏债混合型"和"灵活配置型"，名称相同但归属不同，根据实际权益仓位不同划分

---

## c_hold_value vs c_nav_ratio

- `c_hold_value`（持仓市值）：反映绝对规模影响，用于抱团度
- `c_nav_ratio`（占净值比）：反映基金内部配置比例，用于集中度、重仓股分析

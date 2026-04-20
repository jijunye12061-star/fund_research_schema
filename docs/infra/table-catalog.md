# 表目录

> 路由用途：快速定位"哪张表有我需要的数据"，字段详情见各表 `tables/tb_xxx/SPEC.md`。
>
> **补数起点约定**（详见各表 SPEC）
> - 中间层半年度表：统一 **2015-06-30**
> - 标签层：统一 **2016-12-31**

---

## 数据源层

| 表名 | 说明 | 更新 |
|------|------|------|
| tb_fd_basic_info | 基金基础信息，含主代码 `c_init_code`，所有持仓分析的去重基准 | 按需全量 |
| tb_fd_asset_allocation | 基金各类资产市值与占比（股票/债券/存款等） | 视图，实时 |
| tb_fd_nav_daily | 基金单位/累计/复权净值、区间收益、申赎状态 | 视图，实时 |
| tb_fd_portfolio_stk | 基金股票持仓，`c_style` 区分季报/半年报/年报 | 视图，实时 |
| tb_fd_portfolio_bd | 基金债券持仓 | 视图，实时 |
| tb_fd_manager | 基金经理任职信息 | 按需同步 |
| tb_fd_holder_structure | 基金持有人结构，机构/个人/员工持有比例及份额，含 A/C 各份额 | 视图，实时（DBA 配置中） |
| tb_fd_holder_top10 | 基金前十大持有人明细，含持有人类型/份额/比例 | 视图，实时（DBA 配置中） |
| tb_stk_basic_info | A股证券基本信息，含上市退市日期 | 按需全量 |
| tb_stk_basic_info_hk | 港股证券基本信息 | 按需全量 |
| tb_stk_industry_hk | 港股行业归属（申万/中信/港交所/GICS） | 按需全量 |
| tb_stk_quote_daily | A股日行情，含涨跌幅/换手率/涨跌停 | 视图，实时 |
| tb_stk_quote_daily_hk | 港股日行情，含人民币成交额/PE/PB | 视图，实时 |
| tb_idx_quote_daily | 指数日行情，含开高低收/PE/PB | 视图，实时 |
| tb_trade_calendar | 交易日历，`c_max_trade_date` 是报告期转最近交易日的关键字段 | 按需全量 |
| tb_dict_params | 11 套行业/概念分类代码映射 | 按需全量 |
| tb_bd_basic_info | 债券基础信息，含正股代码 `c_stk_code`、债券类型、发行/上市/退市日 | 视图，实时 |
| tb_cb_analysis | 转债日频估值：转股溢价率、纯债溢价率、平底溢价率、Delta、YTM | 视图，实时 |
| tb_bd_quote_daily | 债券日行情：全价/净价 OHLC、VWAP、成交量/额/笔数、YTM（银行间）| 视图，实时 |

---

## 日频计算层

每个交易日触发。

| 表名 | 说明 |
|------|------|
| tb_stk_industry | A股行业归属快照 |
| tb_stk_concept | A股概念归属快照 |
| tb_fd_perform_abs | 基金绝对收益指标（波动率/夏普/最大回撤等） |

---

## 中间层

标签层的直接上游，`tb_fd_category` 是所有标签表的基准宇宙，**必须最先跑**。

| 表名 | 说明 | 频率 |
|------|------|------|
| tb_fd_category | 基金分类（权益/固收加/债券/混合等八大类） | 季度 |
| tb_fd_ind_weight | 基金行业持仓权重 | 半年度 |
| tb_fd_turnover | 基金换手率 | 半年度 |
| tb_fd_bd_risk_metric | 债券信用/久期指标 | 半年度 |
| tb_stk_crowding_score | 个股抱团度得分（中间计算表） | 半年度 |

---

## 标签层

所有标签表统一从 **2016-12-31** 开始补数。

| 表名 | 说明 | 触发 |
|------|------|------|
| tb_fd_tag_asset | 资产配置标签 | 季度 |
| tb_fd_tag_bd_style | 债券投资风格标签 | 综合 |
| tb_fd_tag_stk_region_sector | 股票区域/板块标签（双触发） | 综合 |
| tb_fd_tag_stk_style | 股票投资风格标签（Barra 因子） | 半年度 |
| tb_fd_tag_stk_portfolio | 股票组合特征标签，7 维 26 字段（双触发） | 综合 |
| tb_fd_tag_cb_style | 转债持仓≥1%基金（001/002/004）转债投资风格标签，5 维 40 字段 | 季度 |

---

## DAG 依赖关系

```
数据源层（视图 + 基础同步）
 │
 ├── 日频：tb_stk_industry / tb_stk_concept / tb_fd_perform_abs
 │
 └── 中间层
      ├── [季度] tb_fd_category  ──────────────────────────────┐
      │                                                         │
      └── [半年度，可并行]                                      │
           tb_fd_ind_weight ──────────────────────────────┐    │
           tb_fd_turnover                                 │    │
           tb_fd_bd_risk_metric                           │    │
               │                                         │    │
               └── tb_stk_crowding_score ─────────────┐  │    │
                                                      ↓  ↓    ↓
                                                  标签层（2016-12-31 起）
```

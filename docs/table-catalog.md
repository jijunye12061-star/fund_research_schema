# 表目录概览

> 26 张表按功能分为四层：**数据源层 → 日频计算层 → 中间层 → 标签层**。
> 字段详情见各表 `tables/tb_xxx/SPEC.md`。
>
> **补数起点约定**
> - 中间层半年度表：统一 **2015-06-30**（21 期）
> - 标签层：统一 **2016-12-31**（确保上游有足够历史数据）

---

## 一、数据源层

无 ETL 调度，实时映射或按需全量同步。

### 视图（实时映射）

| 表名 | 中文名 | 说明 |
|------|--------|------|
| tb_fd_asset_allocation | 基金资产配置 | 股票/债券/买入返售/银行存款等各类资产市值与占比，季度披露 |
| tb_fd_nav_daily | 基金日净值 | 单位/累计/复权净值、不同区间收益率、申赎状态 |
| tb_fd_portfolio_stk | 基金股票持仓 | c_style 01/02/03/04/05/06 区分季报/半年报/年报及披露类型 |
| tb_fd_portfolio_bd | 基金债券持仓 | 持仓债券代码/市值/占比 |
| tb_idx_quote_daily | 指数日行情 | 开高低收/成交量/PE/PB |
| tb_stk_quote_daily | A股日行情 | 涨跌幅/换手率/涨跌停标记 |
| tb_stk_quote_daily_hk | 港股日行情 | 含人民币成交额/市值/PE/PB |
| tb_trade_calendar | 交易日历 | 自然日↔交易日映射，`c_max_trade_date` 是报告期转交易日的关键字段 |

### 基础同步（按需全量）

| 表名 | 中文名 | 说明 |
|------|--------|------|
| tb_fd_basic_info | 基金基础信息 | 基金代码/名称/成立日期/主代码（`c_init_code`）；所有持仓分析的去重基准 |
| tb_stk_basic_info | A股基本信息 | 证券代码/内码/名称/公司代码/上市退市日期 |
| tb_stk_basic_info_hk | 港股基本信息 | 港股证券代码/上市状态 |
| tb_stk_industry_hk | 港股行业归属 | 申万/中信/港交所/GICS 四套行业体系最新归属 |
| tb_dict_params | 字典参数 | 11 套行业分类体系代码映射、概念代码映射等 |

---

## 二、日频计算层

每个交易日触发，DS 以当天日期调用 `run('YYYYMMDD')`。

| 表名 | 中文名 | 依赖 | 补数起点 |
|------|--------|------|----------|
| tb_stk_industry | A股行业归属快照 | 行业事件表 | 2015-01-05 |
| tb_stk_concept | A股概念归属快照 | 概念事件表 | 2015-01-05 |
| tb_fd_perform_abs | 基金绝对收益指标 | tb_fd_nav_daily | 2015-01-05 |

---

## 三、中间层

标签层的直接上游。分季度和半年度两类。

### 季度基础

`tb_fd_category` 是所有标签表的基准宇宙，**必须最先跑**。

| 表名 | 中文名 | 依赖 | 补数起点 | 期数 |
|------|--------|------|----------|------|
| tb_fd_category | 基金分类 | tb_fd_basic_info, tb_fd_asset_allocation | 2015-03-31 | 43 期 |

### 半年度基础（三表可并行）

全持仓数据（`c_style='02'/'04'`）披露后触发（H1+60天 / Annual+90天）。

| 表名 | 中文名 | 依赖 | 补数起点 | 期数 |
|------|--------|------|----------|------|
| tb_fd_ind_weight | 基金行业持仓权重 | tb_fd_portfolio_stk, tb_stk_industry, tb_stk_basic_info(_hk), tb_dict_params | 2015-06-30 | 21 期 |
| tb_fd_turnover | 基金换手率 | tb_fd_portfolio_stk, tb_fd_asset_allocation | 2015-06-30 | 21 期 |
| tb_fd_bd_risk_metric | 债券信用/久期指标 | tb_fd_portfolio_bd | 2015-06-30 | 21 期 |

### 半年度中间（依赖以上半年度基础）

| 表名 | 中文名 | 依赖 | 补数起点 | 期数 |
|------|--------|------|----------|------|
| tb_stk_crowding_score | 个股抱团度得分 | tb_fd_category, tb_fd_basic_info, tb_fd_portfolio_stk | 2015-06-30 | 21 期 |

---

## 四、标签层

所有标签表统一从 **2016-12-31** 开始补数。

| 表名 | 中文名 | 触发频率 | 说明 |
|------|--------|----------|------|
| tb_fd_tag_asset | 资产配置标签 | 季度 | 唯一纯季度标签，仅依赖 tb_fd_category + tb_fd_asset_allocation |
| tb_fd_tag_bd_style | 债券投资风格标签 | 综合 | 季报期可部分计算；半年报期依赖 tb_fd_bd_risk_metric 完整计算 |
| tb_fd_tag_stk_region_sector | 股票区域/板块标签 | 综合（双触发） | 区域字段季度更新；板块字段依赖 tb_fd_ind_weight 半年度更新 |
| tb_fd_tag_stk_style | 股票投资风格标签 | 半年度 | 只用半年报期 Barra 因子数据，半年度触发 |
| tb_fd_tag_stk_portfolio | 股票组合特征标签 | 综合（双触发） | 7 维 26 字段，详见 [调度指南](scheduling-guide.md) |

---

## 五、DAG 依赖关系

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
           tb_fd_turnover ────────────────────────────┐   │    │
           tb_fd_bd_risk_metric                       │   │    │
               │                                     │   │    │
               └── tb_stk_crowding_score ─────────┐  │   │    │
                                                  ↓  ↓   ↓    ↓
                                              标签层（统一起点 2016-12-31）
                                              tb_fd_tag_asset               [纯季度]
                                              tb_fd_tag_bd_style            [综合]
                                              tb_fd_tag_stk_region_sector   [综合]
                                              tb_fd_tag_stk_style           [综合]
                                              tb_fd_tag_stk_portfolio       [综合，双触发]
```

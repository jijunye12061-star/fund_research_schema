# 固收+基金季报解读 — 实施计划

> 计划日期：2026-04-16  
> 对应框架文档：`docs/plans/fi_analysis.md`

---

## 数据可用性结论

| 模块 | 状态 | 备注 |
|------|------|------|
| 一、市场环境 | 可用 | 利率/信用利差需手动补 CSV |
| 二、规模变化 | 可用 | 新发产品份额字段缺失，用户手动提供 |
| 三、资金流向 | 估算 | 无份额表，用规模差估算净申购 |
| 四、业绩表现 | 可用 | tb_fd_perform_abs 覆盖完整 |
| 五、持仓配置 | 可用 | 季报转股期转债全量披露；持有人结构待建表后补入 |

---

## 关键数据注意事项

**转债持仓披露规则**（`tb_fd_portfolio_bd`）：
- `c_bd_type='2'`（转股期可转债）：**季报全量披露**（无数量限制）
- `c_bd_type='1'`（普通债券）：季报仅前5大，半年报/年报全量
- 因此季报做转债分析是可行的，数据质量比预期好

**资金流向估算公式**：
```
净申购（亿）≈ 期末规模 - 期初规模 × (1 + 近3月收益率/100)
```
收益率来源：`tb_fd_perform_abs`（`c_period_code='01'`，取报告期末对应最近交易日）

**持有人结构**：`tb_fd_holder_structure` 尚未建表（列入 Backlog），建好后在模块三/五中补入。

---

## 文件结构

```
analysis/20260416_固收加季报解读/
  config.py           ← 全局参数 + 公共函数（fetch_fi_universe）
  m1_market.py        ← 模块一：市场环境
  m2_scale.py         ← 模块二：规模变化
  m3_flow.py          ← 模块三：资金流向
  m4_perf.py          ← 模块四：业绩表现
  m5_holding.py       ← 模块五：持仓配置
  run_all.py          ← 一键运行所有模块
  manual_data/
    interest_rate.csv   ← 用户手动放入（格式见下）
    new_funds.xlsx      ← 用户手动放入（新发产品数据）
  data/               ← 输出目录（各模块 xlsx）
  README.md
```

---

## config.py（公共层，先完成）

```python
REPORT_DATE = '2025-12-31'    # 当期报告期
PREV_DATE   = '2025-09-30'    # 上期报告期
YEAR_START  = '2025-01-01'    # YTD 起始
PERF_DATE   = '2026-04-15'    # 业绩计算截止日（最新交易日）

# 历史趋势回溯（2020年起，每季度）
HIST_DATES = [
    '2020-03-31','2020-06-30','2020-09-30','2020-12-31',
    '2021-03-31','2021-06-30','2021-09-30','2021-12-31',
    '2022-03-31','2022-06-30','2022-09-30','2022-12-31',
    '2023-03-31','2023-06-30','2023-09-30','2023-12-31',
    '2024-03-31','2024-06-30','2024-09-30','2024-12-31',
    '2025-03-31','2025-06-30','2025-09-30','2025-12-31',
]

# 固收+二级分类代码→名称映射（tb_fd_category c_type1_code='002'）
# 002001 可转债基金 / 002002 混合债券型二级债基 / 002003 偏债混合型
# 002004 灵活配置型（低仓位） / 可能还有其他代码待核实
```

**核心函数**：
```python
def fetch_fi_universe(doris, report_date):
    """获取固收+基金宇宙（主代码去重），含基金简称、公司、经理、成立日期"""
    # tb_fd_category c_type1_code='002' JOIN tb_fd_basic_info
    # WHERE c_init_code = c_fd_code OR c_init_code IS NULL
```

---

## 模块一：市场环境（m1_market.py）

**数据源**：
- `tb_idx_quote_daily` — 主要指数（沪深300/中证500/创业板指/恒生指数/中证转债/中债综合财富）
- `tb_cb_analysis` — 全市场转债转股溢价率中位数
- `manual_data/interest_rate.csv` — 用户手动提供

**手动 CSV 格式**（`manual_data/interest_rate.csv`）：
```
date,indicator,value
2025-09-30,10Y_treasury,2.15
2025-12-31,10Y_treasury,1.60
2025-09-30,AA_spread,82.5
2025-12-31,AA_spread,65.0
```

**输出** `data/m1_market.xlsx`：
- Sheet1: 指数行情（指数名称 / 期初点位 / 期末点位 / 当季涨跌幅% / YTD涨跌幅%）
- Sheet2: 转债估值（期初/期末 转股溢价率中位数、当期分位数）
- Sheet3: 利率与信用利差（读 CSV，如文件不存在则跳过该 Sheet）

---

## 模块二：规模变化（m2_scale.py）

**数据源**：
- `tb_fd_category` + `tb_fd_basic_info` — 基金宇宙
- `tb_fd_asset_allocation`（`c_fund_nav_total`, `c_is_stat=-1`, `c_style` 季报对应值）
- `tb_fd_tag_asset_fi` — `c_eq_risk_level`、`c_stk_cb_strategy`

**输出** `data/m2_scale.xlsx`：
- Sheet1: **基金清单**（代码/简称/二级类型/公司/经理/本期规模/上期规模/规模变化/是否新成立）← 核心基础表
- Sheet2: 分品类汇总（各类型：数量/本期规模/上期规模/环比变化%）
- Sheet3: 基金公司 TOP20（管理规模/市占率%）
- Sheet4: 规模增长 TOP20 产品
- Sheet5: 新发产品（本季 `c_estabdate` 范围内，规模+基本信息；份额列留空，待用户手动填入 `manual_data/new_funds.xlsx`）
- Sheet6: 历史趋势（各报告期总规模亿元+数量，从 HIST_DATES 遍历）
- Sheet7: 按策略分类规模（`c_eq_risk_level` 稳健/均衡/激进 + `c_stk_cb_strategy`）

---

## 模块三：资金流向（m3_flow.py）

**数据源**：
- `tb_fd_asset_allocation`（规模，自行查询，不依赖 m2 输出文件）
- `tb_fd_perform_abs`（`c_period_code='01'` 近3月收益率，取报告期末最近交易日）

**输出** `data/m3_flow.xlsx`：
- Sheet1: 每只基金净申购估算（代码/类型/公司/期初规模/期末规模/近3月收益率%/估算净申购亿/数据备注）
- Sheet2: 分品类汇总（各类型净申购合计）
- Sheet3: 基金公司净申购 TOP10
- Sheet4: 净申购 TOP20 产品

**注意事项**：
- 排除本季新成立基金（无上期规模）
- 报告中标注"估算值，误差来源：分红/拆分/近3月≠精确季度"
- 持有人结构分析暂缺，待 `tb_fd_holder_structure` 建表后补入（见 Backlog）

---

## 模块四：业绩表现（m4_perf.py）

**数据源**：
- `tb_fd_perform_abs`（各区间收益/回撤/夏普）
- 基金宇宙（config.py）

**取数对应关系**：
| 指标 | period_code | 日期 |
|------|------------|------|
| 当季收益率 | 01（近3月） | PERF_DATE |
| YTD 收益率 | 07（今年以来） | PERF_DATE |
| 当季最大回撤 | 01 | PERF_DATE |
| 夏普 / 索提诺 | 01 | PERF_DATE |

**输出** `data/m4_perf.xlsx`：
- Sheet1: 业绩明细（代码/类型/规模/当季收益%/YTD收益%/当季最大回撤%/夏普/同类分位数）
- Sheet2: 分品类业绩统计（10%/25%/50%/75%/90% 分位数 + 正收益占比 + 极差）
- Sheet3: 各品类收益 TOP5（规模 > 1亿筛选）
- Sheet4: 大规模产品业绩盘点（规模 TOP20 产品）
- Sheet5: 基金公司平均收益（规模 TOP20 公司）

---

## 模块五：持仓配置（m5_holding.py）

**数据源**：
- `tb_fd_asset_allocation` — 大类资产仓位
- `tb_fd_portfolio_stk`（季报前10大重仓股）
- `tb_fd_portfolio_bd`（**季报转股期转债全量** `c_bd_type='2'`；普通债券前5大 `c_bd_type='1'`）
- `tb_stk_industry` — 中信一级行业
- `tb_bd_basic_info` — 转债评级、正股代码
- `tb_fd_tag_stk_region_sector` — 板块标签
- `tb_fd_tag_bd_style` — 债券风格标签

**输出** `data/m5_holding.xlsx`：
- Sheet1: 资产配置总览（每只基金：股票%/转债%/权益整体%/港股%，本期+上期）
- Sheet2: 分品类仓位中位数（近4期对比）
- Sheet3: 重仓股明细（基金×股票，含中信一级行业/市值/占净值比）
- Sheet4: 重仓股行业汇总（各行业持仓市值占比，本期+上期+变化，分品类）
- Sheet5: 前十大重仓股排名（按市值汇总，分品类）
- Sheet6: **转股期转债持仓明细**（基金×转债，含评级/正股代码/正股行业）
- Sheet7: 转债评级分布（AAA/AA+/AA 等占比，本期+上期）
- Sheet8: 转债行业分布及增减持（正股行业维度）
- Sheet9: 前20大重仓转债（按持仓市值汇总）
- Sheet10: 债券风格标签汇总（券种/杠杆 分品类分布，`tb_fd_tag_bd_style`）

---

## Backlog — 持有人结构表

> 优先级：中（半年报/年报季更有价值）

**目标**：建 `tb_fd_holder_structure` 表，记录机构/个人持有比例和规模。

**数据来源**：TYTFUND Oracle 源表（待确认表名，可能是 `FUND_HOLDER_STRUCTURE` 或类似），半年报/年报披露。

**Schema 设计（草案）**：
```sql
CREATE TABLE tytdata.tb_fd_holder_structure (
  c_report_date   DATE,
  c_fd_code       VARCHAR(20),
  c_inst_ratio    DECIMAL(12,4)  COMMENT '机构持有比例(%)',
  c_retail_ratio  DECIMAL(12,4)  COMMENT '个人持有比例(%)',
  c_inst_nav      DECIMAL(18,4)  COMMENT '机构持有净值(亿元)',
  c_retail_nav    DECIMAL(18,4)  COMMENT '个人持有净值(亿元)',
  c_updatetime    DATETIME(6)
)
UNIQUE KEY(c_report_date, c_fd_code)
```

**落地步骤**（走 infra 流程）：
1. 确认 Oracle 源表和字段名
2. 建 Doris schema + view
3. 写 insert.py（半年报/年报触发）
4. 建好后在 m3_flow.py 中补入持有人结构 Sheet

---

## 执行顺序

| 阶段 | 任务 | 可并行 |
|------|------|--------|
| 1 | config.py（公共层） | - |
| 2 | m1 / m2 / m4 / m5 | **全部并行** |
| 3 | m3（资金流向） | 并行也可（自行查规模） |
| 4 | run_all.py + README.md | 最后 |
| Backlog | tb_fd_holder_structure 建表 | 独立 infra 任务 |

---

## 验证方式

```bash
# 单模块测试
python analysis/20260416_固收加季报解读/m2_scale.py

# 全量运行
python analysis/20260416_固收加季报解读/run_all.py
```

检查要点：
- 基金总数量约 500-800 只（固收+宇宙的合理范围）
- 抽样1-2只基金的规模/收益率与数据库直查核对
- 转债明细行数 > 重仓股明细行数（季报转债全量，重仓股前10大）

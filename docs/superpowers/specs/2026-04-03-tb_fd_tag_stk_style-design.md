# tb_fd_tag_stk_style 设计文档

## 背景

描述股票型/混合型基金在六个量化风格维度上的得分与标签：市值、价值-成长、动量、盈利、质量。供基金画像、风格归因、AI问答使用。

---

## 数据来源

| 数据 | 来源表 | 字段/条件 |
|------|--------|-----------|
| 基金持仓 | tb_fd_portfolio_stk | c_style IN ('02','04')，近4期半年报 |
| 个股因子 | tb_stk_risk_factor | c_factor_code IN (LNCAP, VALUE, GROWTH, MOMENTUM, PROF, QUALITY) |
| 个股流通市值 | tb_stk_barra_status | c_float_mv，用于 SIZE 阈值计算 |
| 基金范围 | tb_fd_tag_stk_region_sector | 区域标签非"港股"（动量/盈利/质量维度专用） |
| 基金分类 | tb_fd_category | 前四类（001/002/003/004），且近4期有半年报持仓 |

**半年报期定义：** 报告期末为 06-30 或 12-31 的4期，与 tb_fd_tag_stk_region_sector 板块窗口一致。

**持仓去重：** 同一 (fd_code, stk_code, report_date) 多 c_style 时，取 MIN(c_style)（与现有 asset_allocation 处理方式一致）。

**加权方式：** 所有因子得分均以持仓市值（c_hold_value，元）加权，仅保留 A 股持仓（剔除港股标的）。

---

## 字段清单

| 字段 | 类型 | 说明 |
|------|------|------|
| c_report_date | DATE | 报告期 |
| c_fd_code | VARCHAR(20) | 基金代码 |
| c_size_score | DECIMAL(10,4) | 持仓加权平均流通市值（亿元，4期均值） |
| c_size_tag | VARCHAR(10) | 市值标签：大盘/中盘/小盘 |
| c_value_score | DECIMAL(10,4) | 持仓加权 VALUE z-score 均值（4期） |
| c_growth_score | DECIMAL(10,4) | 持仓加权 GROWTH z-score 均值（4期） |
| c_vg_tag | VARCHAR(10) | 价值成长标签：价值/成长/GARP/均衡 |
| c_momentum_score | DECIMAL(10,4) | 持仓加权 MOMENTUM z-score 均值（4期） |
| c_momentum_tag | VARCHAR(10) | 动量标签：高动量/中动量/低动量 |
| c_profit_score | DECIMAL(10,4) | 持仓加权 PROF z-score 均值（4期） |
| c_profit_tag | VARCHAR(10) | 盈利标签：高盈利/中盈利/低盈利 |
| c_quality_score | DECIMAL(10,4) | 持仓加权 QUALITY z-score 均值（4期） |
| c_quality_tag | VARCHAR(10) | 质量标签：高质量/中质量/低质量 |
| c_updatetime | DATETIME(6) | 更新时间 |

---

## 标签计算规则

### 一、市值标签（c_size_tag）

**每期动态阈值（取4期均值）：**

```
全市场 A 股按 c_float_mv 降序排列 → 累加
cval_size_50 = 累计流通市值达到全市场50%时，边界股票的 c_float_mv（亿元）
cval_size_70 = 累计流通市值达到全市场70%时，边界股票的 c_float_mv（亿元）
```

**基金得分：** 持仓加权平均流通市值 = Σ(c_hold_value × c_float_mv_亿) / Σ(c_hold_value)

**分类：**

| 条件 | 标签 |
|------|------|
| 基金得分 > avg(cval_size_50) | 大盘 |
| avg(cval_size_70) < 基金得分 ≤ avg(cval_size_50) | 中盘 |
| 基金得分 ≤ avg(cval_size_70) | 小盘 |

---

### 二、价值-成长标签（c_vg_tag）

**每期动态阈值（取4期均值）：**

```
全市场 A 股截面计算 spread = VALUE z-score − GROWTH z-score
cval_1 = spread 的 67 百分位（上三分位，偏价值方向）
cval_2 = spread 的 33 百分位（下三分位，偏成长方向）
median ≈ 0（VALUE/GROWTH 均已 z-score 标准化，均值=0）
```

**基金得分：**
- fund_value = 持仓加权 VALUE z-score 均值（4期均值）
- fund_growth = 持仓加权 GROWTH z-score 均值（4期均值）
- fund_spread = fund_value − fund_growth

**分类（按优先级顺序）：**

| 条件 | 标签 | 含义 |
|------|------|------|
| fund_value > 0 且 fund_spread ≥ avg(cval_1) | 价值 | 价值占优，成长相对低 |
| fund_growth > 0 且 fund_spread ≤ avg(cval_2) | 成长 | 成长占优，价值相对低 |
| fund_value > 0 且 fund_growth > 0，不满足上面两条 | GARP | 价值成长均较高（合理价格成长） |
| 其余 | 均衡 | 无明显风格偏好 |

---

### 三、动量/盈利/质量标签

与市值/价值-成长不同，这三个维度用**跨基金相对分位**（而非股票级绝对阈值）划分。

**基金得分：**
- 持仓加权对应因子 z-score 均值（4期均值）
- 基金范围：剔除 c_region_tag = '港股' 的基金

**阈值计算：** 计算当期所有符合条件基金得分的 70% / 30% 分位数

| 条件 | 标签（动量/盈利/质量同逻辑） |
|------|------|
| 得分 ≥ 70 分位 | 高动量 / 高盈利 / 高质量 |
| 30 分位 < 得分 < 70 分位 | 中动量 / 中盈利 / 中质量 |
| 得分 ≤ 30 分位 | 低动量 / 低盈利 / 低质量 |

---

## 产出文件

| 文件 | 说明 |
|------|------|
| schema.sql | Doris 建表语句，UNIQUE KEY (c_report_date, c_fd_code) |
| insert.py | 计算逻辑，入口 run(calc_date: str) |
| SPEC.md | 表说明文档 |

---

## 实现要点

1. **分期计算再平均：** 对近4期每期分别算基金得分和阈值，最后取均值，而非把4期持仓混在一起加权
2. **港股标的剔除：** 加权时只用 A 股持仓（tb_stk_barra_status 有数据的即为 A 股，可用 LEFT JOIN 过滤 null）
3. **因子日期对齐：** 用报告期当天的因子值（tb_stk_risk_factor.c_trade_date = c_report_date）
4. **持仓数据量大：** tb_fd_portfolio_stk 每期约 130 万行，用 query_batch 分批处理
5. **季报期复用：** Q1/Q3 无半年报，复用上期结果（UNIQUE KEY 覆盖写入）

---

## 验证方式

1. 取 2025-06-30 跑完后，检查 c_vg_tag 四分类分布是否合理（不应有一类占比 >60%）
2. 检查 c_size_tag 中大盘基金是否确实以大市值股票为主（抽取3-5只核查持仓）
3. c_momentum_tag / c_profit_tag / c_quality_tag 的高/中/低分布预期各约 30%
4. 与 tb_fd_tag_stk_region_sector 对比基金数量，偏差应 <5%（同一基金范围）

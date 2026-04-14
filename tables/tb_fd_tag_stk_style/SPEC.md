# tb_fd_tag_stk_style — 基金股票量化风格标签表

## 基本信息

**一句话定位：** 描述股票型/混合型基金在市值、价值-成长、动量、盈利、质量五个量化维度上的得分与标签，适合回答"找大盘价值基金"、"哪些基金动量风格最强"等问题。

| 项目 | 内容 |
|------|------|
| 主键 | (c_report_date, c_fd_code) |
| 表类型 | 计算型（insert.py 调度） |
| 更新频率 | 季度（每季度末更新，季报期和半年报期共享相同的半年报窗口时结果一致） |
| 基金范围 | tb_fd_category 前四类（001/002/003/004） |
| 历史起点 | 2016-12-31（风险模型因子数据从该期开始） |

**依赖表**: `tb_fd_portfolio_stk` / `tb_stk_risk_factor` / `tb_stk_barra_status` / `tb_fd_tag_stk_region_sector` / `tb_fd_category` / `tb_trade_calendar`

## 字段清单

| 字段名 | 类型 | 单位/说明 |
|--------|------|-----------|
| c_report_date | DATE | 报告期 |
| c_fd_code | VARCHAR(20) | 基金代码 |
| c_size_score | DECIMAL(10,4) | 持仓加权平均流通市值，亿元，近4期半年报均值 |
| c_size_tag | VARCHAR(10) | 市值标签，枚举见下方 |
| c_value_score | DECIMAL(10,4) | 持仓加权 VALUE z-score，近4期半年报均值 |
| c_growth_score | DECIMAL(10,4) | 持仓加权 GROWTH z-score，近4期半年报均值 |
| c_vg_tag | VARCHAR(10) | 价值成长标签，枚举见下方 |
| c_momentum_score | DECIMAL(10,4) | 持仓加权 MOMENTUM z-score，近4期半年报均值 |
| c_momentum_tag | VARCHAR(10) | 动量标签，枚举见下方 |
| c_profit_score | DECIMAL(10,4) | 持仓加权 PROF z-score，近4期半年报均值 |
| c_profit_tag | VARCHAR(10) | 盈利标签，枚举见下方 |
| c_quality_score | DECIMAL(10,4) | 持仓加权 QUALITY z-score，近4期半年报均值 |
| c_quality_tag | VARCHAR(10) | 质量标签，枚举见下方 |
| c_updatetime | DATETIME(6) | 更新时间 |

## 标签规则

### 市值标签（c_size_tag）

**阈值（4期均值）：** 每期全市场A股按 c_float_mv 降序累加，`cval_size_50` = 累计市值达50%时的边界股票流通市值，`cval_size_70` = 70%时边界值。取4期均值得 `avg_50` / `avg_70`。

| 取值 | 条件 |
|------|------|
| `大盘` | c_size_score > avg_50 |
| `中盘` | avg_70 < c_size_score ≤ avg_50 |
| `小盘` | c_size_score ≤ avg_70 |

### 价值-成长标签（c_vg_tag）

**阈值（4期均值）：** 每期全市场 spread = VALUE - GROWTH，`cval_1` = 67%分位，`cval_2` = 33%分位，取4期均值。

基金 fund_spread = c_value_score - c_growth_score（均为4期均值）。

| 取值 | 判断条件（按优先级） |
|------|------|
| `价值` | c_value_score > 0 且 fund_spread ≥ avg_cval_1 |
| `成长` | c_growth_score > 0 且 fund_spread ≤ avg_cval_2 |
| `GARP` | c_value_score > 0 且 c_growth_score > 0，不满足上两条 |
| `均衡` | 其余 |

### 动量/盈利/质量标签

基于**跨基金相对分位**（仅非港股基金），阈值为当期所有非港股基金得分的70%/30%分位。

| 取值 | 条件 |
|------|------|
| `高动量` / `高盈利` / `高质量` | 得分 ≥ 70%分位 |
| `中动量` / `中盈利` / `中质量` | 30%分位 < 得分 < 70%分位 |
| `低动量` / `低盈利` / `低质量` | 得分 ≤ 30%分位 |

> 港股基金不参与打标签（动量/盈利/质量/红利字段为 NULL）。原因：风险模型不含港股标的因子，仅用A股持仓计算得分不具可比性。

## 常用关联表

| 关联表 | 关联字段 | 用途 |
|--------|---------|------|
| tb_fd_basic_info | c_fd_code | 获取基金名称、基金经理 |
| tb_fd_category | (c_report_date, c_fd_code) | 获取基金分类 |
| tb_fd_tag_stk_region_sector | (c_report_date, c_fd_code) | 补充区域/板块标签 |

## 使用示例

```sql
-- 查询最新期大盘价值基金
SELECT s.c_fd_code, b.c_fd_name, s.c_size_score, s.c_value_score
FROM tytdata.tb_fd_tag_stk_style s
JOIN tytdata.tb_fd_basic_info b ON s.c_fd_code = b.c_fd_code
WHERE s.c_report_date = '2025-06-30'
  AND s.c_size_tag = '大盘'
  AND s.c_vg_tag = '价值'
ORDER BY s.c_value_score DESC;

-- 风格分布统计
SELECT c_size_tag, c_vg_tag, COUNT(*) AS cnt
FROM tytdata.tb_fd_tag_stk_style
WHERE c_report_date = '2025-06-30'
GROUP BY c_size_tag, c_vg_tag
ORDER BY cnt DESC;

-- 查询某基金历史风格演变
SELECT c_report_date, c_size_tag, c_vg_tag, c_momentum_tag,
       c_size_score, c_value_score, c_growth_score
FROM tytdata.tb_fd_tag_stk_style
WHERE c_fd_code = '000001'
ORDER BY c_report_date;

-- 找高质量小盘成长基金
SELECT s.c_fd_code, b.c_fd_name,
       s.c_size_score, s.c_growth_score, s.c_quality_score
FROM tytdata.tb_fd_tag_stk_style s
JOIN tytdata.tb_fd_basic_info b ON s.c_fd_code = b.c_fd_code
WHERE s.c_report_date = '2025-06-30'
  AND s.c_size_tag = '小盘'
  AND s.c_vg_tag = '成长'
  AND s.c_quality_tag = '高质量'
ORDER BY s.c_quality_score DESC;
```

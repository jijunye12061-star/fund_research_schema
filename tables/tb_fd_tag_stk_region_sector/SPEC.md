# tb_fd_tag_stk_region_sector — 基金股票投资区域/板块特征标签表

## 基本信息

**一句话定位：** 描述基金的股票投资地域偏好（A股/港股）和板块配置风格（赛道/轮动/均衡），适合回答"找港股基金"、"哪些基金是科技赛道"、"基金的板块配置风格是什么"等问题。

| 项目 | 内容 |
|------|------|
| 主键 | (c_report_date, c_fd_code) |
| 表类型 | 计算型（insert.py 调度） |
| 更新频率 | 季度（半年报/年报后更新，季报期复用上期板块数据） |
| 基金范围 | tb_fd_category 前四类（001/002/003/004），且近8期至少有1期股票持仓 |
| 历史起点 | 2015-06-30 |

## 数据来源

| 特征 | 来源表 | 窗口 |
|------|--------|------|
| 区域特征 | tb_fd_asset_allocation | 近8期季报（含06-30/12-31/03-31/09-30） |
| 板块特征 | tb_fd_ind_weight | 近4期半年报（含06-30/12-31） |

## 字段清单

| 字段名 | 类型 | 单位/说明 |
|--------|------|-----------|
| c_report_date | DATE | 报告期 |
| c_fd_code | VARCHAR(20) | 基金代码 |
| c_hk_ratio_avg | DECIMAL(8,4) | 港股占股票仓位均值，百分比制（5.0 = 5%），近8期季报 |
| c_hk_ratio_latest | DECIMAL(8,4) | 港股占股票仓位最新一期，百分比制 |
| c_region_tag | VARCHAR(10) | 区域标签，枚举见下方 |
| c_sector_cycle | DECIMAL(8,4) | 周期板块权重均值，百分比制，近4期半年报 |
| c_sector_mfg | DECIMAL(8,4) | 中游制造板块权重均值，百分比制 |
| c_sector_tech | DECIMAL(8,4) | 科技板块权重均值，百分比制 |
| c_sector_consumer | DECIMAL(8,4) | 消费板块权重均值，百分比制 |
| c_sector_pharma | DECIMAL(8,4) | 医药板块权重均值，百分比制 |
| c_sector_fin | DECIMAL(8,4) | 金融地产板块权重均值，百分比制 |
| c_sector_chg | DECIMAL(8,4) | 板块权重变动指标，百分比制（越大说明板块轮动越频繁） |
| c_sector_tag | VARCHAR(10) | 板块标签，枚举见下方；指数基金或无行业数据时为 null |
| c_sector_pref | VARCHAR(20) | 板块偏好，仅赛道型基金有值，其余为空字符串 |

## 标签规则

### 区域标签（c_region_tag）

基于 `c_hk_ratio_avg`（近8期季报港股占股票仓位均值）划分：

| 取值 | 条件 | 含义 |
|------|------|------|
| `A股` | 均值 < 20% | 主要投资A股 |
| `均衡` | 20% ≤ 均值 ≤ 60% | A股与港股均有配置 |
| `港股` | 均值 > 60% | 主要投资港股 |

港股占比计算：`c_stk_hk_connect_ratio / c_stk_total_ratio × 100`

### 板块标签（c_sector_tag / c_sector_pref）

**第一步：计算板块权重变动指标 c_sector_chg**

各板块近4期半年报权重的加权平均绝对变化量：

```
sector_chg = Σ(各板块权重均值 × 各板块权重绝对变化均值) / Σ(各板块权重均值)
```

指标越大说明基金的板块配置变动越剧烈（轮动越频繁）。

**第二步：打标签（按优先级顺序判断）**

| 取值 | 判断条件 | 含义 |
|------|---------|------|
| `轮动型` | chg ≥ 20% 且 max(板块均值) × (1 − chg/100) ≤ 50% | 板块配置变动明显，无持续主导板块 |
| `赛道型` | max(板块均值) > 50%（非轮动型） | 长期重仓单一板块，同时标注 c_sector_pref |
| `均衡型` | 其余 | 板块配置相对分散且稳定 |

**c_sector_pref 取值枚举**（仅赛道型基金有值）：

`周期` / `中游制造` / `科技` / `消费` / `医药` / `金融地产`

## 常用关联表

| 关联表 | 关联字段 | 用途 |
|--------|---------|------|
| tb_fd_basic_info | c_fd_code | 获取基金名称、基金经理 |
| tb_fd_category | (c_report_date, c_fd_code) | 获取基金分类（股票型/混合型等） |
| tb_fd_tag_stk_style | (c_report_date, c_fd_code) | 补充市值风格（大盘/中盘/小盘）和价值成长标签 |
| tb_fd_tag_stk_portfolio | (c_report_date, c_fd_code) | 补充集中度、换手、主动管理等组合特征 |

## 使用示例

```sql
-- 查询最新期科技赛道基金（附基金名称）
SELECT t.c_fd_code, b.c_fd_name, t.c_sector_tech, t.c_hk_ratio_avg
FROM tytdata.tb_fd_tag_stk_region_sector t
JOIN tytdata.tb_fd_basic_info b ON t.c_fd_code = b.c_fd_code
WHERE t.c_report_date = '2025-06-30'
  AND t.c_sector_tag = '赛道型'
  AND t.c_sector_pref = '科技'
ORDER BY t.c_sector_tech DESC;

-- 查询港股基金分布（按区域+板块交叉）
SELECT c_region_tag, c_sector_tag, COUNT(*) AS cnt
FROM tytdata.tb_fd_tag_stk_region_sector
WHERE c_report_date = '2025-06-30'
GROUP BY c_region_tag, c_sector_tag
ORDER BY cnt DESC;

-- 查询某基金历史板块风格演变
SELECT c_report_date, c_sector_tag, c_sector_pref,
       c_sector_tech, c_sector_consumer, c_sector_pharma
FROM tytdata.tb_fd_tag_stk_region_sector
WHERE c_fd_code = '000001'
ORDER BY c_report_date;

-- 找均衡配置的A股基金（无明显板块偏好）
SELECT t.c_fd_code, b.c_fd_name
FROM tytdata.tb_fd_tag_stk_region_sector t
JOIN tytdata.tb_fd_basic_info b ON t.c_fd_code = b.c_fd_code
WHERE t.c_report_date = '2025-06-30'
  AND t.c_region_tag = 'A股'
  AND t.c_sector_tag = '均衡型';
```

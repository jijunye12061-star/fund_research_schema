# tb_fd_tag_stk_region_sector - 基金股票投资区域/板块特征标签表

## 基本信息

- **主键**: (c_report_date, c_fd_code)
- **表类型**: 计算型
- **更新频率**: 季度（半年报/年报后更新）
- **基金范围**: tb_fd_category 前四类 (001/002/003/004)

## 数据来源

| 特征 | 来源表 | 窗口 |
|------|--------|------|
| 区域特征 | tb_fd_asset_allocation | 近8期季报(01/02/03/04) |
| 板块特征 | tb_fd_ind_weight | 近4期半年报(02/04) |

## 字段清单

| 字段名 | 类型 | 注释 |
|--------|------|------|
| c_report_date | DATE | 报告期 |
| c_fd_code | VARCHAR(20) | 基金代码 |
| c_hk_ratio_avg | DECIMAL(8,4) | 港股占股票比均值(%, 近8期季报) |
| c_hk_ratio_latest | DECIMAL(8,4) | 港股占股票比最新一期(%) |
| c_region_tag | VARCHAR(10) | 区域标签 |
| c_sector_cycle | DECIMAL(8,4) | 周期板块权重均值(%) |
| c_sector_mfg | DECIMAL(8,4) | 中游制造板块权重均值(%) |
| c_sector_tech | DECIMAL(8,4) | 科技板块权重均值(%) |
| c_sector_consumer | DECIMAL(8,4) | 消费板块权重均值(%) |
| c_sector_pharma | DECIMAL(8,4) | 医药板块权重均值(%) |
| c_sector_fin | DECIMAL(8,4) | 金融地产板块权重均值(%) |
| c_sector_chg | DECIMAL(8,4) | 板块权重变动指标(%) |
| c_sector_tag | VARCHAR(10) | 板块标签 |
| c_sector_pref | VARCHAR(20) | 板块偏好(赛道型专用) |

## 标签规则

### 区域标签

| 港股占比均值 | 标签 |
|------------|------|
| < 20% | A股 |
| 20% ~ 60% | 均衡 |
| > 60% | 港股 |

港股占比 = `c_stk_hk_connect_ratio / c_stk_total_ratio × 100`

### 板块标签

板块权重变动指标：各板块环比变化绝对值均值，按板块权重均值加权：

```
sector_chg = Σ(avg_weight_s × mean_abs_change_s) / Σ(avg_weight_s)
```

| 判断条件 | 标签 |
|---------|------|
| chg ≥ 20% 且 max(avg_weight) × (1 - chg/100) ≤ 50% | 轮动型 |
| max(avg_weight) > 50% 且非轮动型 | 赛道型（标注偏好板块）|
| 其余 | 均衡型 |

## 配置文件

`config/sector_mapping.yaml`：中信一级行业(025) → 六大板块映射

## 使用示例

```sql
-- 查询最新期赛道型基金及偏好板块分布
SELECT c_sector_pref, COUNT(*) AS cnt
FROM tytdata.tb_fd_tag_stk_region_sector
WHERE c_report_date = '2024-06-30'
  AND c_sector_tag = '赛道型'
GROUP BY c_sector_pref ORDER BY cnt DESC;

-- 查询港股基金
SELECT c_fd_code, c_hk_ratio_avg, c_hk_ratio_latest
FROM tytdata.tb_fd_tag_stk_region_sector
WHERE c_report_date = '2024-06-30'
  AND c_region_tag = '港股'
ORDER BY c_hk_ratio_avg DESC;

-- 查询某基金历史板块演变
SELECT c_report_date, c_sector_tag, c_sector_pref,
       c_sector_tech, c_sector_consumer, c_sector_pharma
FROM tytdata.tb_fd_tag_stk_region_sector
WHERE c_fd_code = '000001'
ORDER BY c_report_date;
```

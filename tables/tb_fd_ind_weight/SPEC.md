# tb_fd_ind_weight - 基金行业持仓权重表

## 基本信息

- **主键**: (c_report_date, c_fd_code, c_ind_code)
- **表类型**: 计算型
- **更新频率**: 季度（半年报/年报披露后）
- **分区方式**: 按月动态分区，每分区3桶

**依赖表**: `tb_fd_portfolio_stk` / `tb_stk_industry` / `tb_stk_industry_hk`

## 字段清单

| 字段名           | 类型           | 注释             | 说明                   |
|---------------|--------------|----------------|----------------------|
| c_report_date | DATE         | 报告期            | 半年报/年报截止日            |
| c_fd_code     | VARCHAR(20)  | 基金代码           | 六位代码                 |
| c_ind_code    | VARCHAR(6)   | 中信一级行业代码       | 025前缀，统一口径           |
| c_ind_name    | VARCHAR(50)  | 中信一级行业名称       | 来自 tb_dict_params    |
| c_weight      | DECIMAL(8,4) | 行业持仓权重(%)      | 行业持仓市值/股票投资总市值×100   |
| c_updatetime  | DATETIME(6)  | 更新时间           | 系统自动生成               |

## 注意事项

- 仅半年报/年报期（06-30 / 12-31）有数据；季报（01/03）只披露前10大持仓，行业分布不完整
- `c_weight` 以**全部股票持仓市值**为分母（含港股、含行业未知股票），与研报口径一致
- 港股行业统一转为025中信一级代码；极少量无法归属的港股持仓不计入分子但计入分母（影响极小）

## 使用示例

```sql
-- 查某基金某期的行业分布
SELECT c_ind_name, c_weight
FROM tytdata.tb_fd_ind_weight
WHERE c_fd_code = '000001'
  AND c_report_date = '2024-06-30'
ORDER BY c_weight DESC;

-- 近4期各行业权重均值（用于板块标签计算）
SELECT c_fd_code, c_ind_code, c_ind_name, AVG(c_weight) AS avg_weight
FROM tytdata.tb_fd_ind_weight
WHERE c_report_date IN ('2023-06-30', '2023-12-31', '2024-06-30', '2024-12-31')
GROUP BY c_fd_code, c_ind_code, c_ind_name;

-- 前5大行业权重之和（行业集中度）
SELECT c_fd_code,
       SUM(c_weight) AS top5_ratio
FROM (SELECT c_fd_code, c_weight,
             ROW_NUMBER() OVER (PARTITION BY c_fd_code ORDER BY c_weight DESC) AS rn
      FROM tytdata.tb_fd_ind_weight
      WHERE c_report_date = '2024-06-30') t
WHERE rn <= 5
GROUP BY c_fd_code;
```

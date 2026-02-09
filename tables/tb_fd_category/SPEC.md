# tb_fd_category - 基金基础分类表(组内)

## 基本信息

- **主键**: (c_fd_code, c_report_date)
- **更新频率**: 定期更新
- **数据范围**: 基金内部分类标准

## 字段清单

| 字段名           | 类型          | 注释     | 说明     |
|---------------|-------------|--------|--------|
| c_fd_code     | VARCHAR(20) | 基金代码   | 六位代码   |
| c_report_date | DATE        | 报告日期   | 每个季度分类 |
| c_type1_code  | VARCHAR(10) | 一级分类代码 | 见枚举值   |
| c_type1_name  | VARCHAR(50) | 一级分类名称 | -      |
| c_type2_code  | VARCHAR(10) | 二级分类代码 | 见枚举值   |
| c_type2_name  | VARCHAR(50) | 二级分类名称 | -      |
| c_updatetime  | DATETIME(6) | 更新时间   | 自动更新   |

## 枚举值

### 基金分类体系

| 一级分类           | 二级分类              | 说明                                          |
|----------------|-------------------|---------------------------------------------|
| **001 权益基金**   |                   |                                             |
|                | 001001 主动权益型基金    | 所有"普通股票型基金"及近一年平均权益仓位>70%的偏股混合/平衡混合/灵活配置型基金 |
|                | 001002 指数增强型基金    | 增强指数型基金                                     |
|                | 001003 被动指数型基金    | 被动指数型基金                                     |
| **002 固收加基金**  |                   |                                             |
|                | 002001 可转债基金      | 名称带"转债"或可转债投资比例平均>60%                       |
|                | 002002 混合债券型基金    | 原混合债券型基金,排除近四期平均仓位<1%的基金                    |
|                | 002003 偏债混合型基金    | 近四期权益仓位最大值≤40%或均值≤30%的偏债混合型基金               |
|                | 002004 灵活配置型基金    | 近四期权益仓位最大值≤40%或均值≤30%的灵活配置型基金               |
| **003 债券型基金**  |                   |                                             |
|                | 003001 短期纯债型基金    | -                                           |
|                | 003002 中长期纯债型基金   | -                                           |
|                | 003003 指数型债券基金    | -                                           |
|                | 003004 债券增强型基金    | 近四期权益仓位均值<1%                                |
| **004 混合型基金**  |                   | 不在权益基金和固收加基金范围内的其他原混合型基金                    |
|                | 004001 偏股混合型基金    | -                                           |
|                | 004002 平衡混合型基金    | -                                           |
|                | 004003 偏债混合型基金    | -                                           |
|                | 004004 灵活配置型基金    | -                                           |
|                | 004005 其他混合型基金    | -                                           |
| **005 QDII基金** |                   |                                             |
|                | 005001 QDII股票型基金  | -                                           |
|                | 005002 QDII混合型基金  | -                                           |
|                | 005003 QDII债券型基金  | -                                           |
|                | 005004 QDII-FOF   | -                                           |
|                | 005005 QDII商品型基金  | -                                           |
|                | 005006 QDII-REITs | -                                           |
| **006 FOF基金**  |                   |                                             |
|                | 006001 股票型FOF     | -                                           |
|                | 006002 混合型FOF     | -                                           |
|                | 006003 债券型FOF     | -                                           |
|                | 006004 其他FOF      | 原养老目标FOF                                    |
| **007 另类投资基金** |                   |                                             |
|                | 007001 基础设施REITs  | -                                           |
|                | 007002 商品型基金      | -                                           |
|                | 007003 量化对冲基金     | -                                           |
| **008 货币型基金**  |                   |                                             |
|                | 008001 传统货币型基金    | -                                           |
|                | 008002 浮动净值型货币基金  | -                                           |

## 使用示例

```sql
-- 查询某基金最新分类
SELECT c_fd_code, c_type1_name, c_type2_name, c_report_date
FROM tytdata.tb_fd_category
WHERE c_fd_code = '000001'
ORDER BY c_report_date DESC
LIMIT 1;

-- 统计各一级分类基金数量
SELECT c_type1_name, COUNT(DISTINCT c_fd_code) as fund_count
FROM tytdata.tb_fd_category
WHERE c_report_date = (SELECT MAX(c_report_date) FROM tytdata.tb_fd_category)
GROUP BY c_type1_name
ORDER BY fund_count DESC;

-- 查询2024-12-31截面上主动权益型基金列表
SELECT DISTINCT c_fd_code
FROM tytdata.tb_fd_category
WHERE c_type2_code = '001001'
  AND c_report_date = '2024-12-31';

-- 查询某基金分类变更历史
SELECT c_report_date, c_type1_name, c_type2_name
FROM tytdata.tb_fd_category
WHERE c_fd_code = '000001'
ORDER BY c_report_date DESC;
```

## 备注
每个报告期截面基金均需满足
- 成立满一年
- 转型后基金以转型日作为起始日计算
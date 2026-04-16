# tb_fd_holder_structure — 基金持有人结构表

## 概述

存储每只基金每个报告期的机构/个人持有比例及份额，来源为 Oracle `FUND_HOLDCHANGE`。

- **KEY**: `(c_report_date, c_fd_code)`
- **表类型**: 视图（Oracle 实时映射，DBA 配置 catalog 后生效）
- **更新频率**: 半年报/年报披露后（约 06-30+60天、12-31+90天），少数特殊情况有非标准日期
- **基金范围**: 全量，含 A/C/B 各份额，**不做主代码去重**

---

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `c_report_date` | DATE | 报告日期（主流基金为 06-30 或 12-31；新成立/清盘基金可为非标准日期） |
| `c_fd_code` | VARCHAR(20) | 基金代码（源表 `FCODE`） |
| `c_notice_date` | DATE | 公告日期 |
| `c_total_holder` | NUMBER | 持有人总户数 |
| `c_holder_per` | NUMBER | 平均每户持有份额（份） |
| `c_inst_share` | FLOAT | 机构持有份额（份） |
| `c_inst_ratio` | FLOAT | 机构持有比例（%） |
| `c_retail_share` | FLOAT | 个人持有份额（份） |
| `c_retail_ratio` | FLOAT | 个人持有比例（%） |
| `c_employee_share` | FLOAT | 基金公司员工持有份额（份） |
| `c_employee_ratio` | FLOAT | 基金公司员工持有比例（%） |
| `c_feeder_share` | FLOAT | 联接基金持有份额（份，ETF 场景） |
| `c_feeder_ratio` | FLOAT | 联接基金持有比例（%，ETF 场景） |

---

## 注意事项

**A/C 份额机构比例不一致**

同一基金的 A 份额和 C 份额在本表中各有独立记录（`c_fd_code` 不同，`c_init_code` 相同）。两者的机构/个人比例通常差异显著：

- C 份额：申购费率低，散户偏好，`c_retail_ratio` 通常更高
- A 份额：机构和定投散户混合，`c_inst_ratio` 相对更高
- ETF 联接 A/C 同理

分析时若需基金整体口径，需按份额规模加权合并，或直接用 `c_init_code` 为主代码的 A 份额代表基金整体（近似）。

**非标准报告日期**

`c_report_date` 对绝大多数基金为 06-30 / 12-31。以下情况会出现其他日期：
- 基金清盘：清算日前强制披露
- 新成立基金：首次成立公告时披露

查询标准半年报/年报数据时，建议过滤：
```sql
WHERE TO_CHAR(c_report_date, 'MM-DD') IN ('06-30', '12-31')
```

**字段单位**：份额字段单位为"份"（非万份），数值可能达 10^9 量级。

**员工持有字段**：`c_employee_ratio` 可用于判断基金公司是否自购旗下产品，但 NULL 较多（部分基金未披露）。

**联接基金字段**：`c_feeder_ratio` 在近期数据中多为 NULL，历史数据（2010年前）有部分有效值。

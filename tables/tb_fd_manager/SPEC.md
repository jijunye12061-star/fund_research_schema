# tb_fd_manager - 基金经理任职信息

## 基本信息

| 项目 | 内容 |
|------|------|
| 表类型 | 视图（Oracle 实时映射） |
| 数据来源 | `TYTFUND.FUND_BS_FEXECUTIVE` |
| 过滤条件 | `EISDEL = '0'` |
| 主键逻辑 | `c_fd_code + c_person_code + c_start_date + c_post` |
| 总记录数 | ~83372 条 |
| 数据时效 | 实时（视图直查 Oracle） |

## 数据来源

Oracle 表 `TYTFUND.FUND_BS_FEXECUTIVE` 记录基金经理/助理/代理的历任信息，每条记录对应一段任职关系。

**关联 SPEC：**
- `tb_fd_basic_info.c_manager_code`：当前在任经理的 `c_person_code` 逗号拼接（如 `'30040527,30786034'`），可用 `FIND_IN_SET` 关联
- `tb_fd_nav_daily`：通过 `c_fd_code + c_start_date` 可取任职首日净值，计算任职以来收益率

## 字段清单

| 字段 | 类型 | 注释 | 说明 |
|------|------|------|------|
| c_record_id | BIGINT | 记录内码 | Oracle 表主键（FNID），每条记录唯一 |
| c_fd_code | VARCHAR(6) | 基金代码 | |
| c_person_code | VARCHAR(8) | 基金经理编码 | 跨基金唯一，对应 c_manager_code |
| c_mgr_name | VARCHAR(100) | 基金经理姓名 | |
| c_post | VARCHAR(20) | 职位 | 见枚举值 |
| c_job_title | VARCHAR(60) | 职称 | 注册金融分析师/注册会计师等，部分为 NULL |
| c_start_date | DATE | 任职开始日期 | |
| c_end_date | DATE | 离任日期 | NULL 表示当前在任 |
| c_is_current | TINYINT | 是否在任 | -1=在任, 0=离任 |
| c_notice_date | DATE | 公告日期 | |
| c_leave_reason | VARCHAR(200) | 离任原因 | 自由文本，内容不规范 |
| c_sex | VARCHAR(2) | 性别 | 男/女 |
| c_birth_date | DATE | 出生日期 | 较多 NULL 或近似值（如1975-01-01） |
| c_education | VARCHAR(40) | 学历 | 学士/硕士/博士/MBA 等 |
| c_exp_years | FLOAT | 从业年限 | 行业从业总年限，非该基金任职时长 |
| c_resume | TEXT | 简历 | NCLOB，长文本，基本全量有值 |
| c_remark | TEXT | 附注 | CLOB，仅约 4253 条非空（休假代管等特殊说明） |
| c_source | VARCHAR(50) | 数据来源 | 见枚举值 |

## 枚举值

### c_post（职位）

| 值 | 含义 |
|----|------|
| 基金经理 | 正式基金经理 |
| 基金经理助理 | 助理级别，辅助管理 |
| 代理基金经理 | 临时代理（如正式经理休假期间） |

### c_is_current（是否在任）

| 值 | 含义 |
|----|------|
| -1 | 当前在任 |
| 0 | 已离任 |

注意：Oracle 原值为 -1 而非 1，查询时用 `c_is_current = -1` 过滤在任。

### c_source（数据来源）

季度报告 / 临时公告 / 招募说明书(更新) / 扩募说明书 / 中期报告

## 业务说明

### 同一人多段任期

同一人可在同一基金先任**基金经理助理**，后正式升任**基金经理**，各自一条记录。
典型案例：郑晓辉(30040527)在 000001：
- 2024-12-24 ~ 2024-12-26：`c_post='基金经理助理'`（定报期间短暂记录）
- 2024-12-26 ~ NULL：`c_post='基金经理'`（正式升任，c_is_current=-1）

因此主键需包含 `c_post`；按任职时长分析时应指定 `c_post='基金经理'`。

### 基金代码去重

A股基金同一策略通常有 A/C/R/I 等多份额，各份额均会记录经理信息，导致同一经理在同一策略下出现多条重复记录。分析基金经理覆盖规模时，建议结合 `tb_fd_basic_info.c_init_code` 去重，只取主份额。

### c_exp_years 含义

`c_exp_years` 是从业总年限（PATICTERM 字段），反映该经理在基金行业工作的总年限，**不是**在该基金的任职时长。任职时长用 `DATEDIFF(COALESCE(c_end_date, CURDATE()), c_start_date)` 计算。

## 使用示例

```sql
-- 1. 某基金的历任基金经理（仅正式经理）
SELECT c_mgr_name, c_start_date, c_end_date, c_is_current, c_leave_reason
FROM tytdata.tb_fd_manager
WHERE c_fd_code = '000001' AND c_post = '基金经理'
ORDER BY c_start_date;

-- 2. 某基金经理当前管理的基金 + 任职天数
SELECT c_fd_code, c_start_date,
       DATEDIFF(CURDATE(), c_start_date) AS tenure_days
FROM tytdata.tb_fd_manager
WHERE c_person_code = '30038120'
  AND c_post = '基金经理'
  AND c_is_current = -1;

-- 3. 某基金经理任职以来的复权净值收益率
SELECT m.c_fd_code, m.c_mgr_name, m.c_start_date,
       ROUND((n_end.c_nav_adj / n_start.c_nav_adj - 1) * 100, 2) AS ret_pct
FROM tytdata.tb_fd_manager m
JOIN tytdata.tb_fd_nav_daily n_start
    ON m.c_fd_code = n_start.c_fd_code AND n_start.c_trade_date = m.c_start_date
JOIN tytdata.tb_fd_nav_daily n_end
    ON m.c_fd_code = n_end.c_fd_code AND n_end.c_trade_date = CURDATE()
WHERE m.c_person_code = '30038120'
  AND m.c_post = '基金经理'
  AND m.c_is_current = -1;

-- 4. 通过 c_manager_code 反查当前经理完整信息
SELECT b.c_fd_code, b.c_fd_name, m.c_mgr_name, m.c_start_date,
       DATEDIFF(CURDATE(), m.c_start_date) AS tenure_days,
       LEFT(m.c_resume, 200) AS resume_preview
FROM tytdata.tb_fd_basic_info b
JOIN tytdata.tb_fd_manager m
    ON FIND_IN_SET(m.c_person_code, b.c_manager_code) > 0
WHERE b.c_fd_code = '000001'
  AND m.c_is_current = -1
  AND m.c_post = '基金经理';
```

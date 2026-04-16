# tb_fd_holder_structure — 持有人结构表建设计划

> **状态**: 待执行 | **日期**: 2026-04-16 | **负责人**: jijunye  
> ⚠️ 完工后删除此文件

---

## Context

固收+季报解读（`docs/plans/fi_analysis_impl.md` 模块三）需要机构/个人持有比例分析。持有人结构数据每期半年报/年报披露，Oracle TYTFUND 中有对应源表，需同步至 Doris。

---

## 阶段一：Oracle 源表探查（先做）

**需要确认的源表**（建议先用 Oracle 连接查）：

```sql
-- 候选表名，在 TYTFUND 中依次尝试
SELECT TABLE_NAME FROM ALL_TABLES
WHERE OWNER = 'TYTFUND'
  AND TABLE_NAME LIKE '%HOLDER%'
ORDER BY TABLE_NAME;
```

常见命名可能是：`FUND_SH_HOLDERSTRUC`、`FUND_BA_HOLDERSTRUC`、`FUND_IV_HOLDERINFO`

**需要确认的字段**：

| 预期含义 | 确认字段名 |
|---------|----------|
| 基金代码 | 待确认（通常 `FUNDCODE`） |
| 报告期 | 待确认（通常 `ENDDATE`） |
| 机构持有比例 | 待确认 |
| 个人持有比例 | 待确认 |
| 机构持有份额 | 待确认（可能有） |
| 个人持有份额 | 待确认（可能有） |
| 总份额 | 待确认 |
| 报表类别 | 待确认（区分半年报/年报，类似 c_style） |

```sql
-- 探查样本（确认表名后替换）
SELECT * FROM TYTFUND.FUND_SH_HOLDERSTRUC
WHERE ROWNUM <= 10
ORDER BY ENDDATE DESC;
```

---

## 阶段二：Doris 表设计

### schema.sql（草案，待源表字段确认后微调）

```sql
CREATE TABLE tytdata.`tb_fd_holder_structure` (
  `c_report_date`    DATE          NOT NULL COMMENT '报告期（06-30 或 12-31）',
  `c_fd_code`        VARCHAR(20)   NOT NULL COMMENT '基金代码',
  `c_inst_ratio`     DECIMAL(10,4) NULL     COMMENT '机构持有比例(%)',
  `c_retail_ratio`   DECIMAL(10,4) NULL     COMMENT '个人持有比例(%)',
  `c_inst_share`     DECIMAL(20,4) NULL     COMMENT '机构持有份额（万份，如源表有）',
  `c_retail_share`   DECIMAL(20,4) NULL     COMMENT '个人持有份额（万份，如源表有）',
  `c_total_share`    DECIMAL(20,4) NULL     COMMENT '总份额（万份，如源表有）',
  `c_notice_date`    DATE          NULL     COMMENT '公告日期',
  `c_updatetime`     DATETIME(6)   NULL     DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE=OLAP
UNIQUE KEY(`c_report_date`, `c_fd_code`)
COMMENT '基金持有人结构表（机构/个人比例）[机构研究]'
DISTRIBUTED BY HASH(`c_fd_code`, `c_report_date`) BUCKETS 3
PROPERTIES (
  "replication_allocation" = "tag.location.default: 3",
  "enable_unique_key_merge_on_write" = "true",
  "light_schema_change" = "true"
);
```

**设计说明**：
- 主键 `(c_report_date, c_fd_code)` — 每基金每期一行
- 仅半年报/年报披露，即 `c_report_date` 只会出现 `XX-06-30` 和 `XX-12-31`
- `c_inst_ratio + c_retail_ratio ≈ 100`（可能有误差，源数据四舍五入）
- 份额字段如源表无则留 NULL，不影响主要用途（比例分析）

---

## 阶段三：insert.py 设计

### 调度触发条件

```python
def should_run(calc_date: str) -> bool:
    """仅在半年报/年报报告期触发"""
    d = datetime.strptime(calc_date, '%Y-%m-%d')
    return d.month == 6 and d.day == 30 or d.month == 12 and d.day == 31
```

### 核心逻辑

```python
def _fetch_oracle(oracle, report_date):
    """从 Oracle 源表取持有人结构"""
    sql = """
    SELECT
        FUNDCODE   AS c_fd_code,
        ENDDATE    AS c_report_date,
        -- 字段名待源表确认后填入
        INST_RATIO   AS c_inst_ratio,
        RETAIL_RATIO AS c_retail_ratio,
        NOTICEDATE AS c_notice_date
    FROM TYTFUND.FUND_SH_HOLDERSTRUC   -- 表名待确认
    WHERE ENDDATE = :1
      AND EISDEL = '0'
    """
    return oracle.query(sql, report_date)
```

### 写入策略

- **UNIQUE KEY 覆盖写入**（`doris.insert()`）
- 每次按 `c_report_date` 整期重写，支持重跑幂等

---

## 阶段四：SPEC.md（建表完成后补写）

字段说明、JOIN 示例、业务用途参照 `tables/tb_fd_turnover/SPEC.md` 格式。

---

## 后续与 fi_analysis 的衔接

持有人结构表建好后，在 `analysis/20260416_固收加季报解读/m3_flow.py` 中补入：

- Sheet5（新增）：持有人结构（机构 vs 个人持有比例，分品类）
- Sheet6（新增）：机构偏好产品 vs 个人偏好产品的规模变动对比

---

## 历史数据补充

- 历史起点建议：**2018-12-31**（固收+分析惯例起点）
- 补数命令：`python tables/tb_fd_holder_structure/insert.py 2018-12-31`（按期循环）
- 半年度更新，历史数据约 15 期（2018-2025）

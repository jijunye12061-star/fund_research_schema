-- ============================================================
-- 债券信用评级与久期指标表
-- 合并自 FUND_IV_HOLDCREDITRISKO + FUND_IV_RISKSENSITIVE
-- ============================================================
CREATE TABLE tb_fd_bd_risk_metric (
    c_report_date DATE COMMENT '报告日期',
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    -- 信用评级-短期(RATETYPE=100): 101高 + 102低 + 300未评级 = 99合计
    c_short_high_mv DECIMAL(20,4) COMMENT '短期高评级(A-1)债券市值(万元)',
    c_short_low_mv DECIMAL(20,4) COMMENT '短期低评级(A-1以下)债券市值(万元)',
    c_short_unrated_mv DECIMAL(20,4) COMMENT '短期未评级债券市值(万元)',
    -- 信用评级-长期(RATETYPE=200): 201高 + 202低 + 300未评级 = 99合计
    c_long_high_mv DECIMAL(20,4) COMMENT '长期高评级(AAA)债券市值(万元)',
    c_long_low_mv DECIMAL(20,4) COMMENT '长期低评级(AAA以下)债券市值(万元)',
    c_long_unrated_mv DECIMAL(20,4) COMMENT '长期未评级债券市值(万元)',
    -- 信用评级-汇总占比(短期+长期合并计算)
    c_high_credit_ratio DECIMAL(10,4) COMMENT '高信用评级占比(%), (A-1 + AAA) / 合计',
    c_low_credit_ratio DECIMAL(10,4) COMMENT '低信用评级占比(%), (A-1以下 + AAA以下) / 合计',
    c_unrated_credit_ratio DECIMAL(10,4) COMMENT '未评级占比(%), (短期未评级 + 长期未评级) / 合计',
    -- 久期: 基于利率敏感性分析反推
    -- 原始数据含利率上升/下降两个方向的净值变动，取绝对值合计后除以变动比例合计和债券市值得到久期
    c_bond_mv DECIMAL(20,4) COMMENT '债券投资市值(万元)',  -- 来源FUND_IV_ASSETALLOCT.BSUM
    c_duration DECIMAL(10,4) COMMENT '久期(年)',  -- = SUM(ABS(净值变动)) / SUM(变动比例) / 债券市值 * 100
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '债券信用评级与久期指标表'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

-- ============================================================
-- 债券投资风格标签表
-- ============================================================
DROP TABLE IF EXISTS tb_fd_tag_bd_style;

CREATE TABLE tb_fd_tag_bd_style (
    c_report_date DATE COMMENT '报告日期',
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_is_locked_fund VARCHAR(10) COMMENT '是否定开基金(1是/0否)',
    -- 券种风格（近八期季报）
    c_rate_bd_pos_avg DECIMAL(10,4) COMMENT '利率债仓位均值(%)',
    c_credit_bd_pos_avg DECIMAL(10,4) COMMENT '信用债仓位均值(%)',
    c_fin_bd_pos_avg DECIMAL(10,4) COMMENT '金融债仓位均值(%)',
    c_rate_bd_chg_avg DECIMAL(10,4) COMMENT '利率债仓位变动均值(%)',
    c_credit_bd_chg_avg DECIMAL(10,4) COMMENT '信用债仓位变动均值(%)',
    c_bd_type_style VARCHAR(30) COMMENT '券种风格标签',
    c_bd_type_timing VARCHAR(10) COMMENT '券种择时标签',
    -- 杠杆风格（近八期季报）
    c_leverage_avg DECIMAL(10,4) COMMENT '杠杆率均值',
    c_leverage_chg_avg DECIMAL(10,4) COMMENT '杠杆率变动均值(绝对值)',
    c_leverage_pref VARCHAR(10) COMMENT '杠杆偏好标签',
    c_leverage_timing VARCHAR(10) COMMENT '杠杆择时标签',
    -- 信用风格（近四个半年报期）
    c_high_credit_avg DECIMAL(10,4) COMMENT '高信用评级占比均值(%)',
    c_low_credit_avg DECIMAL(10,4) COMMENT '低信用评级占比均值(%)',
    c_low_credit_chg_avg DECIMAL(10,4) COMMENT '低信用评级变动均值(%)',
    c_credit_pref VARCHAR(10) COMMENT '信用偏好标签',
    c_credit_timing VARCHAR(10) COMMENT '信用择时标签',
    -- 久期风格（近四个半年报期）
    c_duration_avg DECIMAL(10,4) COMMENT '久期均值(年)',
    c_duration_chg_avg DECIMAL(10,4) COMMENT '久期变动均值(年)',
    c_duration_pref VARCHAR(10) COMMENT '久期偏好标签',
    c_duration_timing VARCHAR(10) COMMENT '久期择时标签',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '债券投资风格标签表'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
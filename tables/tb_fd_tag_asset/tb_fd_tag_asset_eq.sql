-- ============================================================
-- 权益基金资产配置标签表
-- ============================================================
DROP TABLE IF EXISTS tb_fd_tag_asset_eq;

CREATE TABLE tb_fd_tag_asset_eq (
    c_report_date DATE COMMENT '报告日期',
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_stk_pos_avg DECIMAL(8,4) COMMENT '股票仓位均值(%)',
    c_stk_pos_chg_avg DECIMAL(8,4) COMMENT '股票仓位变动均值(%)',
    c_stk_pos_level VARCHAR(20) COMMENT '股票仓位等级',
    c_stk_timing VARCHAR(10) COMMENT '股票择时标签',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '权益基金资产配置标签表'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

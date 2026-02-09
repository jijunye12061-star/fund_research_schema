-- ============================================================
-- 固收+基金资产配置标签表
-- ============================================================
DROP TABLE IF EXISTS tb_fd_tag_asset_fi;

CREATE TABLE tb_fd_tag_asset_fi (
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_report_date DATE COMMENT '报告期',
    c_stk_pos_avg DECIMAL(8,4) COMMENT '股票仓位均值(%)',
    c_cb_pos_avg DECIMAL(8,4) COMMENT '转债仓位均值(%)',
    c_eq_pos_avg DECIMAL(8,4) COMMENT '权益仓位均值(%)',
    c_stk_pos_chg_avg DECIMAL(8,4) COMMENT '股票仓位变动均值(%)',
    c_cb_pos_chg_avg DECIMAL(8,4) COMMENT '转债仓位变动均值(%)',
    c_eq_risk_level VARCHAR(10) COMMENT '风险特征标签',
    c_stk_cb_strategy VARCHAR(30) COMMENT '股票转债策略标签',
    c_stk_timing VARCHAR(10) COMMENT '股票择时标签',
    c_cb_timing VARCHAR(10) COMMENT '转债择时标签',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_fd_code, c_report_date)
COMMENT '固收+基金资产配置标签表'
DISTRIBUTED BY HASH(c_fd_code)
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
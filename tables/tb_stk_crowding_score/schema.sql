CREATE TABLE tytdata.tb_stk_crowding_score
(
    c_report_date      DATE           COMMENT '报告期(06-30或12-31)',
    c_stk_code         VARCHAR(20)    COMMENT '股票代码',
    c_total_hold_mv    DECIMAL(20,4)  COMMENT '全市场权益基金持仓市值合计(元)',
    c_crowd_score_mkt  DECIMAL(10,4)  COMMENT '全市场抱团度得分(百分位排名,0~1)',
    c_updatetime       DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_stk_code)
COMMENT '个股抱团度得分表[机构研究]'
DISTRIBUTED BY HASH(c_stk_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

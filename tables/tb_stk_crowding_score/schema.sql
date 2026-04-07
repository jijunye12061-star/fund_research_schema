-- ============================================================
-- 个股抱团度得分表
-- 全市场(MKT)及各基金公司维度的A股持仓集中度百分位排名
-- 半年报期计算，供 tb_fd_tag_stk_portfolio 加权聚合至基金维度
-- ============================================================
CREATE TABLE tytdata.tb_stk_crowding_score
(
    c_report_date    DATE           COMMENT '报告期(06-30或12-31)',
    c_company_code   VARCHAR(20)    COMMENT '基金公司代码，MKT=全市场',
    c_stk_code       VARCHAR(20)    COMMENT '股票代码',
    c_total_hold_mv  DECIMAL(20,4)  COMMENT '持仓市值合计(元)',
    c_crowd_score    DECIMAL(10,4)  COMMENT '抱团度得分(范围内百分位排名,0~1)',
    c_updatetime     DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_company_code, c_stk_code)
COMMENT '个股抱团度得分表[机构研究]'
DISTRIBUTED BY HASH(c_stk_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

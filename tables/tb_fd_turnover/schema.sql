CREATE TABLE tytdata.tb_fd_turnover
(
    c_report_date      DATE           COMMENT '报告期(06-30或12-31)',
    c_fd_code          VARCHAR(20)    COMMENT '基金代码',
    c_buy_amount       DECIMAL(20,4)  COMMENT '半年度买入股票成本(元)',
    c_sell_amount      DECIMAL(20,4)  COMMENT '半年度卖出股票收入(元)',
    c_avg_stk_mv       DECIMAL(20,4)  COMMENT '三期股票投资市值均值(元)',
    c_turnover_rate    DECIMAL(10,4)  COMMENT '半年度双边换手率(%)',
    c_updatetime       DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '基金股票交易换手率表[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

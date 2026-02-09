DROP TABLE IF EXISTS tb_fd_perform_abs;

CREATE TABLE tb_fd_perform_abs (
    c_fd_code        VARCHAR(20) NOT NULL COMMENT '基金代码',
    c_trade_date     DATE NOT NULL COMMENT '交易日期',
    c_period_code    VARCHAR(10) NOT NULL COMMENT '计算区间代码',
    c_period_ret     DECIMAL(18,4) COMMENT '区间收益率(%)',
    c_ann_ret        DECIMAL(18,4) COMMENT '年化收益率(%)',
    c_ann_vol        DECIMAL(18,4) COMMENT '年化波动率(%)',
    c_up_side_vol    DECIMAL(18,4) COMMENT '上行波动率(%)',
    c_down_side_vol  DECIMAL(18,4) COMMENT '下行波动率(%)',
    c_mdd            DECIMAL(12,4) COMMENT '最大回撤(%)',
    c_sharpe         DECIMAL(18,4) COMMENT '夏普比率',
    c_calmar         DECIMAL(18,4) COMMENT '卡尔玛比率',
    c_sortino        DECIMAL(18,4) COMMENT '索提诺比率',
    c_skewness       DECIMAL(18,4) COMMENT '偏度',
    c_kurtosis       DECIMAL(18,4) COMMENT '峰度',
    c_break_ratio    DECIMAL(12,4) COMMENT '净值创新高天数比例(%)',
    c_updatetime     DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_fd_code, c_trade_date, c_period_code)
COMMENT '基金业绩表现-绝对指标'
DISTRIBUTED BY HASH(c_fd_code)
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
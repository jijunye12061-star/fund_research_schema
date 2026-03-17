-- ============================================================
-- A股股票行业归属表(日频宽表)
-- 每行一个(交易日, 股票), 各分类体系三级代码各一列
-- 截断前6位=一级, 前9位=二级, 完整12位=三级
-- ============================================================
CREATE TABLE tytdata.tb_stk_industry (
    c_trade_date DATE COMMENT '交易日期',
    c_stk_code VARCHAR(20) COMMENT '证券代码',
    c_citic_code VARCHAR(12) COMMENT '中信行业代码(三级,025前缀)',
    c_sw_code VARCHAR(12) COMMENT '申万行业代码(三级,029/011前缀)',
    c_updatetime datetime(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_trade_date, c_stk_code)
COMMENT 'A股股票行业归属表(日频)[机构研究]'
PARTITION BY RANGE(c_trade_date) ()
DISTRIBUTED BY HASH(c_stk_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "MONTH",
    "dynamic_partition.start" = "-150",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1",
    "dynamic_partition.create_history_partition" = "true"
);
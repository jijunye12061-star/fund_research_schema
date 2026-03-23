-- ============================================================
-- A股股票概念归属表(日频长表)
-- 每行一个(交易日, 股票, 概念), 一股多概念
-- 概念名称通过 tb_dict_params (c_param_type='概念板块') 关联
-- ============================================================
CREATE TABLE tytdata.tb_stk_concept (
    c_trade_date    DATE         COMMENT '交易日期',
    c_stk_code      VARCHAR(20)  COMMENT '证券代码',
    c_concept_code  VARCHAR(12)  COMMENT '概念代码(007前缀)',
    c_updatetime    DATETIME(6)  NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_trade_date, c_stk_code, c_concept_code)
COMMENT 'A股股票概念归属表(日频)[机构研究]'
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
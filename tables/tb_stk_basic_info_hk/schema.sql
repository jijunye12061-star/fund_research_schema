-- 港股基本信息表
-- 数据来源: Oracle TYTFUND.CDSY_SECUCODE
-- 更新频率: 每日

CREATE TABLE tytdata.`tb_stk_basic_info_hk` (
  `c_stk_code` VARCHAR(20) NULL COMMENT '证券代码',
  `c_inner_code` VARCHAR(100) NULL COMMENT '证券内码',
  `c_company_code` VARCHAR(100) NULL COMMENT '公司代码',
  `c_stk_name` VARCHAR(200) NULL COMMENT '证券简称',
  `c_stk_type` VARCHAR(50) NULL COMMENT '证券类型',
  `c_trade_market` VARCHAR(50) NULL COMMENT '交易市场',
  `c_list_date` DATE NULL COMMENT '上市日期',
  `c_delist_date` DATE NULL COMMENT '退市日期',
  `c_list_status` VARCHAR(20) NULL COMMENT '上市状态',
  `c_updatetime` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE=OLAP
UNIQUE KEY(`c_stk_code`)
COMMENT '港股基本信息表[机构研究]'
DISTRIBUTED BY HASH(`c_stk_code`) BUCKETS 1
PROPERTIES (
"replication_allocation" = "tag.location.default: 3",
"storage_format" = "V2",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true"
);
-- 基金基础信息表
-- 数据来源: Oracle TYTFUND (FUND_JBXX + FUND_BS_OFINFO + DIM_FD_INIT_CODE + FUND_BS_ATYPE + FUND_BS_CFINFO)
-- 更新频率: 每日

CREATE TABLE tytdata.`tb_fd_basic_info` (
  `c_fd_code` VARCHAR(20) NULL COMMENT '基金代码',
  `c_short_name` VARCHAR(100) NULL COMMENT '基金简称',
  `c_full_name` VARCHAR(200) NULL COMMENT '基金全称',
  `c_estabdate` date NULL COMMENT '成立日期',
  `c_terminate_date` date NULL COMMENT '终止日期',
  `c_terminate_reason` VARCHAR(100) NULL COMMENT '终止原因',
  `c_class1_code` VARCHAR(10) NULL COMMENT '一级分类代码',
  `c_class1_name` VARCHAR(50) NULL COMMENT '一级分类名称',
  `c_class2_code` VARCHAR(10) NULL COMMENT '二级分类代码',
  `c_class2_name` VARCHAR(50) NULL COMMENT '二级分类名称',
  `c_class3_code` VARCHAR(10) NULL COMMENT '三级分类代码',
  `c_class3_name` VARCHAR(50) NULL COMMENT '三级分类名称',
  `c_manager_code` VARCHAR(100) NULL COMMENT '基金经理代码',
  `c_manager_name` VARCHAR(100) NULL COMMENT '基金经理名称',
  `c_custodian_code` VARCHAR(50) NULL COMMENT '托管银行代码',
  `c_custodian_name` VARCHAR(100) NULL COMMENT '托管银行',
  `c_company_code` VARCHAR(50) NULL COMMENT '基金公司代码',
  `c_company_name` VARCHAR(100) NULL COMMENT '基金公司简称',
  `c_invest_scope` TEXT NULL COMMENT '投资范围',
  `c_invest_standard` TEXT NULL COMMENT '投资标准',
  `c_purchase_status` VARCHAR(20) NULL COMMENT '申购状态',
  `c_redeem_status` VARCHAR(20) NULL COMMENT '赎回状态',
  `c_fund_nature` VARCHAR(50) NULL COMMENT '基金性质',
  `c_transform_date` date NULL COMMENT '转型生效日期',
  `c_regular_open_status` VARCHAR(10) NULL COMMENT '定开情况(1是0否)',
  `c_min_hold_period` DECIMAL(18, 2) NULL COMMENT '最短持有期(月)',
  `c_mgmt_fee_rate` VARCHAR(20) NULL COMMENT '基金管理费率',
  `c_custodian_fee_rate` VARCHAR(20) NULL COMMENT '基金托管费率',
  `c_sales_fee_rate` VARCHAR(20) NULL COMMENT '基金销售服务费率',
  `c_init_code` VARCHAR(20) NULL COMMENT '初始代码',
  `c_updatetime` datetime(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE=OLAP
UNIQUE KEY(`c_fd_code`)
COMMENT '基金基础信息表[机构研究]'
DISTRIBUTED BY HASH(`c_fd_code`) BUCKETS 1
PROPERTIES (
"replication_allocation" = "tag.location.default: 3",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false"
);

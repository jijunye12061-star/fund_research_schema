CREATE TABLE tytdata.`tb_fd_category` (
  `c_report_date` date NULL COMMENT '报告日期',
  `c_fd_code` VARCHAR(20) NULL COMMENT '基金代码',
  `c_type1_code` VARCHAR(10) NULL COMMENT '一级分类代码',
  `c_type1_name` VARCHAR(50) NULL COMMENT '一级分类名称',
  `c_type2_code` VARCHAR(10) NULL COMMENT '二级分类代码',
  `c_type2_name` VARCHAR(50) NULL COMMENT '二级分类名称',
  `c_updatetime` datetime(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE=OLAP
UNIQUE KEY(`c_report_date`, `c_fd_code`)
COMMENT '基金基础分类表(组内)[机构研究]'
DISTRIBUTED BY HASH(`c_fd_code`, `c_report_date`) BUCKETS 3
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

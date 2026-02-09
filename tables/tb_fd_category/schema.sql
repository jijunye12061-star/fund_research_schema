DROP TABLE IF EXISTS tb_fd_category;

CREATE TABLE tb_fd_category (
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_report_date DATE COMMENT '报告日期',
    c_type1_code VARCHAR(10) COMMENT '一级分类代码',
    c_type1_name VARCHAR(50) COMMENT '一级分类名称',
    c_type2_code VARCHAR(10) COMMENT '二级分类代码',
    c_type2_name VARCHAR(50) COMMENT '二级分类名称',
    c_updatetime     DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_fd_code, c_report_date)
COMMENT '基金基础分类表(组内)'
DISTRIBUTED BY HASH(c_fd_code, c_report_date)
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
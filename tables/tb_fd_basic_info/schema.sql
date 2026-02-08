-- 基金基础信息表
-- 数据来源: Oracle TYTFUND (FUND_JBXX + FUND_BS_OFINFO + DIM_FD_INIT_CODE + FUND_BS_ATYPE + FUND_BS_CFINFO)
-- 更新频率: 每日

DROP TABLE IF EXISTS tb_fd_basic_info;

CREATE TABLE tb_fd_basic_info (
    c_fd_code VARCHAR(20) COMMENT '基金代码',
    c_short_name VARCHAR(100) COMMENT '基金简称',
    c_full_name VARCHAR(200) COMMENT '基金全称',
    c_estabdate DATE COMMENT '成立日期',
    c_terminate_date DATE COMMENT '终止日期',
    c_terminate_reason VARCHAR(100) COMMENT '终止原因',
    c_class1_code VARCHAR(10) COMMENT '一级分类代码',
    c_class1_name VARCHAR(50) COMMENT '一级分类名称',
    c_class2_code VARCHAR(10) COMMENT '二级分类代码',
    c_class2_name VARCHAR(50) COMMENT '二级分类名称',
    c_class3_code VARCHAR(10) COMMENT '三级分类代码',
    c_class3_name VARCHAR(50) COMMENT '三级分类名称',
    c_manager_code VARCHAR(100) COMMENT '基金经理代码',
    c_manager_name VARCHAR(100) COMMENT '基金经理名称',
    c_custodian_code VARCHAR(50) COMMENT '托管银行代码',
    c_custodian_name VARCHAR(100) COMMENT '托管银行',
    c_company_code VARCHAR(50) COMMENT '基金公司代码',
    c_company_name VARCHAR(100) COMMENT '基金公司简称',
    c_invest_scope TEXT COMMENT '投资范围',
    c_invest_standard TEXT COMMENT '投资标准',
    c_purchase_status VARCHAR(20) COMMENT '申购状态',
    c_redeem_status VARCHAR(20) COMMENT '赎回状态',
    c_fund_nature VARCHAR(50) COMMENT '基金性质',
    c_transform_date DATE COMMENT '转型生效日期',
    c_regular_open_status VARCHAR(10) COMMENT '定开情况(1是0否)',
    c_min_hold_period DECIMAL(18,2) COMMENT '最短持有期(月)',
    c_mgmt_fee_rate VARCHAR(20) COMMENT '基金管理费率',
    c_custodian_fee_rate VARCHAR(20) COMMENT '基金托管费率',
    c_sales_fee_rate VARCHAR(20) COMMENT '基金销售服务费率',
    c_init_code VARCHAR(20) COMMENT '初始代码',
    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_fd_code)
COMMENT '基金基础信息表'
DISTRIBUTED BY HASH(c_fd_code)
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
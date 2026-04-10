-- 基金经理任职信息（临时物化表，DBA 建视图后可替换）
-- 数据来源：TYTFUND.FUND_BS_FEXECUTIVE
-- 更新方式：全量覆盖（sync_fd_manager.py）
CREATE TABLE tytdata.tb_fd_manager (
    c_start_date    DATE            COMMENT '任职开始日期',
    c_person_code   VARCHAR(8)      NOT NULL COMMENT '基金经理编码',
    c_fd_code       VARCHAR(6)      NOT NULL COMMENT '基金代码',
    c_post          VARCHAR(20)     COMMENT '职位(基金经理/基金经理助理/代理基金经理)',
    c_mgr_name      VARCHAR(100)    COMMENT '基金经理姓名',
    c_job_title     VARCHAR(60)     COMMENT '职称',
    c_end_date      DATE            COMMENT '离任日期(NULL=在任)',
    c_is_current    TINYINT         COMMENT '是否在任(-1在任/0离任)',
    c_notice_date   DATE            COMMENT '公告日期',
    c_leave_reason  VARCHAR(200)    COMMENT '离任原因',
    c_sex           VARCHAR(2)      COMMENT '性别',
    c_birth_date    DATE            COMMENT '出生日期',
    c_education     VARCHAR(40)     COMMENT '学历',
    c_exp_years     FLOAT           COMMENT '从业年限',
    c_resume        TEXT            COMMENT '简历(截取前2000字符)',
    c_remark        TEXT            COMMENT '附注',
    c_source        VARCHAR(50)     COMMENT '数据来源'
) UNIQUE KEY(c_start_date, c_person_code, c_fd_code, c_post)
COMMENT '基金经理任职信息[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 1",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

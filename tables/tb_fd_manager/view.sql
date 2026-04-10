-- 基金经理任职信息
-- 数据来源：TYTFUND.FUND_BS_FEXECUTIVE
-- 表类型：视图（Oracle 实时映射）
CREATE VIEW tytdata.tb_fd_manager (
    c_record_id     COMMENT '记录内码',
    c_fd_code       COMMENT '基金代码',
    c_person_code   COMMENT '基金经理编码',
    c_mgr_name      COMMENT '基金经理姓名',
    c_post          COMMENT '职位(基金经理/基金经理助理/代理基金经理)',
    c_job_title     COMMENT '职称',
    c_start_date    COMMENT '任职开始日期',
    c_end_date      COMMENT '离任日期(NULL=在任)',
    c_is_current    COMMENT '是否在任(-1在任/0离任)',
    c_notice_date   COMMENT '公告日期',
    c_leave_reason  COMMENT '离任原因',
    c_sex           COMMENT '性别',
    c_birth_date    COMMENT '出生日期',
    c_education     COMMENT '学历',
    c_exp_years     COMMENT '从业年限',
    c_resume        COMMENT '简历',
    c_remark        COMMENT '附注',
    c_source        COMMENT '数据来源'
) COMMENT '基金经理任职信息[机构研究]' AS
SELECT
    a.FNID          AS c_record_id,
    a.FUNDCODE      AS c_fd_code,
    a.PERSONCODE    AS c_person_code,
    a.NAME          AS c_mgr_name,
    a.POST          AS c_post,
    a.JOBTITLE      AS c_job_title,
    a.CHANGEDATE    AS c_start_date,
    a.ENDDATE       AS c_end_date,
    a.ISPOSITION    AS c_is_current,
    a.NOTICEDATE    AS c_notice_date,
    a.LEAVEREASON   AS c_leave_reason,
    a.SEX           AS c_sex,
    a.BIRTHDATE     AS c_birth_date,
    a.EDUCATION     AS c_education,
    a.PATICTERM     AS c_exp_years,
    a.RESUME        AS c_resume,
    a.REMARK        AS c_remark,
    a.SOURCE        AS c_source
FROM TYTFUND.FUND_BS_FEXECUTIVE a
WHERE a.EISDEL = '0'

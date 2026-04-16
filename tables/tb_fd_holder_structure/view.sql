-- 基金持有人结构（机构/个人比例）
-- 数据来源：TYTFUND.FUND_HOLDCHANGE
-- 表类型：视图（Oracle 实时映射）
-- 注意：PDATE 对主流基金为标准报告期（06-30/12-31）；新成立/清盘基金会有非标准日期
CREATE VIEW tytdata.tb_fd_holder_structure (
    c_report_date    COMMENT '报告日期',
    c_fd_code        COMMENT '基金代码',
    c_notice_date    COMMENT '公告日期',
    c_total_holder   COMMENT '持有人总户数',
    c_holder_per     COMMENT '平均每户份额',
    c_inst_share     COMMENT '机构持有份额',
    c_inst_ratio     COMMENT '机构持有比例(%)',
    c_retail_share   COMMENT '个人持有份额',
    c_retail_ratio   COMMENT '个人持有比例(%)',
    c_employee_share COMMENT '员工持有份额',
    c_employee_ratio COMMENT '员工持有比例(%)',
    c_feeder_share   COMMENT '联接基金持有份额',
    c_feeder_ratio   COMMENT '联接基金持有比例(%)'
) COMMENT '基金持有人结构表[机构研究]' AS
SELECT
    PDATE          AS c_report_date,
    FCODE          AS c_fd_code,
    NOTICEDATE     AS c_notice_date,
    TOTALHOLDER    AS c_total_holder,
    HOLDERPER      AS c_holder_per,
    INSTHOLD       AS c_inst_share,
    PCTINSTHOLD    AS c_inst_ratio,
    PEISONHOLD     AS c_retail_share,
    PCTPEISONHOLD  AS c_retail_ratio,
    EMPLOYEHOLD    AS c_employee_share,
    PCTEMPLOYEHOLD AS c_employee_ratio,
    FUNDHOLD       AS c_feeder_share,
    PCTFUNDHOLD    AS c_feeder_ratio
FROM TYTFUND.FUND_HOLDCHANGE
WHERE EISDEL = '0'

-- 基金前十大持有人明细
-- 数据来源：TYTFUND.FUND_HR_HOLDERTOP10
-- 表类型：视图（Oracle 实时映射）
-- c_style 枚举：02=半年报（06-30）、04=年报（12-31）、07=非定期（新成立/清盘，极少，仅 1999-2002 年早期封闭式基金）
CREATE VIEW tytdata.tb_fd_holder_top10 (
    c_report_date  COMMENT '报告日期',
    c_fd_code      COMMENT '基金代码',
    c_rank         COMMENT '持有人名次',
    c_style        COMMENT '报表类别',
    c_holder_name  COMMENT '持有人名称',
    c_holder_type  COMMENT '持有人类型',
    c_hold_share   COMMENT '持有份额',
    c_hold_ratio   COMMENT '持有比例(%)',
    c_notice_date  COMMENT '公告日期'
) COMMENT '基金前十大持有人明细表[机构研究]' AS
SELECT
    CHANGEDATE AS c_report_date,
    FUNDCODE   AS c_fd_code,
    RANK       AS c_rank,
    STYLE      AS c_style,
    SNAME      AS c_holder_name,
    HOLDERTYPE AS c_holder_type,
    HOLDFE     AS c_hold_share,
    RATIO      AS c_hold_ratio,
    NOTICEDATE AS c_notice_date
FROM TYTFUND.FUND_HR_HOLDERTOP10
WHERE EISDEL = '0'

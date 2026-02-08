CREATE VIEW tytdata.tb_fd_portfolio_bd (
    c_fd_code COMMENT '基金代码',
    c_report_date COMMENT '报告日期',
    c_bd_code COMMENT '债券代码',
    c_bd_type COMMENT '债券类型(1债券2转股期可转债)',
    c_style COMMENT '报表类别',
    c_notice_date COMMENT '公告日期',
    c_bd_inner_code COMMENT '债券内码',
    c_bd_name COMMENT '债券名称',
    c_hold_num COMMENT '持仓数量',
    c_hold_value COMMENT '持仓市值',
    c_nav_ratio COMMENT '占净值比例',
    c_is_stat COMMENT '是否参与统计'
) COMMENT '基金债券投资组合表' AS
SELECT
    FUNDCODE as c_fd_code,
    ENDDATE as c_report_date,
    BONDCODE as c_bd_code,
    BONDTYPE as c_bd_type,
    STYLE as c_style,
    NOTICEDATE as c_notice_date,
    INNERCODE as c_bd_inner_code ,
    BONDNAME as c_bd_name,
    BONDNUM as c_hold_num,
    BONDVALUE as c_hold_value,
    PCTNV as c_nav_ratio,
    ISSTAT as c_is_stat
FROM TYTFUND.FUND_IV_BONDINVESTO
WHERE EISDEL = '0'
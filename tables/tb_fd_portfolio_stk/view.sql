CREATE VIEW tytdata.tb_fd_portfolio_stk (
    c_fd_code COMMENT '基金代码',
    c_report_date COMMENT '期末日期',
    c_stk_code COMMENT '股票代码',
    c_style COMMENT '报表类别',
    c_invest_type COMMENT '投资类型',
    c_notice_date COMMENT '公告日期',
    c_inner_code COMMENT '股票内码',
    c_hold_value COMMENT '持仓市值',
    c_hold_share COMMENT '持仓股数',
    c_nav_ratio COMMENT '占净值比例',
    c_is_stat COMMENT '是否合并统计'
) COMMENT '基金持有股票明细' AS
SELECT
    FUNDCODE as c_fd_code,
    ENDDATE as c_report_date,
    STOCKCODE as c_stk_code,
    STYLE as c_style,
    INVESTTYPE as c_invest_type,
    NOTICEDATE as c_notice_date,
    EMSECURITYVARIETYCODE as c_inner_code,
    HOLDVALUE as c_hold_value,
    HOLDSHARE as c_hold_share,
    PCTNV as c_nav_ratio,
    ISSTAT as c_is_stat
FROM TYTFUND.FUND_IV_STOCKINVESTO
WHERE EISDEL = '0'
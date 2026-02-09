CREATE VIEW tytdata.tb_trade_calendar (
    c_trade_date COMMENT '交易日期',
    c_is_trade COMMENT '是否交易日',
    c_is_week_end COMMENT '是否周末交易日',
    c_is_month_end COMMENT '是否月末交易日',
    c_is_quarter_end COMMENT '是否季末交易日',
    c_is_year_end COMMENT '是否年末交易日',
    c_pre_1d COMMENT '前1个交易日',
    c_pre_1w COMMENT '前1周交易日',
    c_pre_1m COMMENT '前1月交易日',
    c_pre_3m COMMENT '前3月交易日',
    c_pre_6m COMMENT '前6月交易日',
    c_pre_1y COMMENT '前1年交易日',
    c_pre_2y COMMENT '前2年交易日',
    c_pre_3y COMMENT '前3年交易日',
    c_pre_5y COMMENT '前5年交易日'
) COMMENT '交易日历表' AS
SELECT
    TRADE_DT as c_trade_date,
    IS_D as c_is_trade,
    IS_W as c_is_week_end,
    IS_M as c_is_month_end,
    IS_Q as c_is_quarter_end,
    IS_Y as c_is_year_end,
    PRE_D as c_pre_1d,
    PRE_W as c_pre_1w,
    PRE_1M as c_pre_1m,
    PRE_3M as c_pre_3m,
    PRE_6M as c_pre_6m,
    PRE_1Y as c_pre_1y,
    PRE_2Y as c_pre_2y,
    PRE_3Y as c_pre_3y,
    PRE_5Y as c_pre_5y
FROM TYTFUND.QT_TRADE_CALENDAR
WHERE C_ISDEL = '0'
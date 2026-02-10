CREATE VIEW tytdata.tb_trade_calendar (
    c_date          COMMENT '自然日期',
    c_is_trade       COMMENT '是否交易日',
    c_prev_trade_date COMMENT '上一个交易日',
    c_max_trade_date  COMMENT '当日的最近交易日'
) COMMENT '交易日历表' AS
SELECT
    SCAL            AS c_date,
    ISOM            AS c_is_trade,
    LASTTDAY        AS c_prev_trade_date,
    MAXTDAY         AS c_max_trade_date
FROM TYTFUND.CUST_CALENDER
WHERE EISDEL = '0'
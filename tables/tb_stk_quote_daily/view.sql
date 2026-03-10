CREATE VIEW tytdata.tb_stk_quote_daily (
    c_trade_date    COMMENT '交易日期',
    c_stk_code      COMMENT '股票代码',
    c_open          COMMENT '开盘价',
    c_high          COMMENT '最高价',
    c_low           COMMENT '最低价',
    c_close         COMMENT '收盘价',
    c_pre_close     COMMENT '昨收价',
    c_chg           COMMENT '涨跌额',
    c_pct_chg       COMMENT '涨跌幅(%)',
    c_volume        COMMENT '成交量(股)',
    c_amount        COMMENT '成交金额(元)',
    c_turnover      COMMENT '换手率(%)',
    c_is_limit_up   COMMENT '是否涨停',
    c_is_limit_down COMMENT '是否跌停'
) COMMENT '股票日行情（A股）' AS
SELECT
    TDATE         AS c_trade_date,
    SECUCODE      AS c_stk_code,
    OPEN          AS c_open,
    HIGH          AS c_high,
    LOW           AS c_low,
    NEW           AS c_close,
    LCLOSE        AS c_pre_close,
    PCHG1         AS c_chg,
    CHG           AS c_pct_chg,
    TVOL          AS c_volume,
    TVAL          AS c_amount,
    TURNRATE      AS c_turnover,
    IS_LIMIT_UP   AS c_is_limit_up,
    IS_LIMIT_DOWN AS c_is_limit_down
FROM TYTFUND.TRAD_SK_DAILY_JC
WHERE EISDEL = '0';
CREATE VIEW tytdata.tb_stk_quote_daily_hk (
    c_trade_date COMMENT '交易日期',
    c_stk_code   COMMENT '股票代码',
    c_open       COMMENT '开盘价',
    c_high       COMMENT '最高价',
    c_low        COMMENT '最低价',
    c_close      COMMENT '收盘价',
    c_pre_close  COMMENT '昨收价',
    c_chg        COMMENT '涨跌额',
    c_pct_chg    COMMENT '涨跌幅(%)',
    c_volume     COMMENT '成交量(股)',
    c_amount     COMMENT '成交金额(港元)',
    c_amount_rmb COMMENT '成交金额(人民币)',
    c_turnover   COMMENT '换手率(%)',
    c_mv         COMMENT '港股市值',
    c_pe         COMMENT '市盈率',
    c_pb         COMMENT '市净率'
) COMMENT '港股日行情' AS
SELECT
    TDATE    AS c_trade_date,
    SECUCODE AS c_stk_code,
    TOPEN    AS c_open,
    HIGH     AS c_high,
    LOW      AS c_low,
    NEW      AS c_close,
    LCLOSE   AS c_pre_close,
    CHG      AS c_chg,
    PCHG     AS c_pct_chg,
    TNUM     AS c_volume,
    TAMT     AS c_amount,
    TAMTRMB  AS c_amount_rmb,
    TURNRATE AS c_turnover,
    HKMV     AS c_mv,
    PE       AS c_pe,
    PB       AS c_pb
FROM TYTFUND.TRAD_SK_HKDAILY
WHERE EISDEL = '0';
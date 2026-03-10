CREATE VIEW tytdata.tb_idx_quote_daily (
    c_trade_date COMMENT '交易日期',
    c_idx_code   COMMENT '指数代码',
    c_inner_code COMMENT '证券内码',
    c_open       COMMENT '开盘价',
    c_high       COMMENT '最高价',
    c_low        COMMENT '最低价',
    c_close      COMMENT '收盘价',
    c_pre_close  COMMENT '昨收价',
    c_volume     COMMENT '成交量',
    c_amount     COMMENT '成交金额',
    c_pe         COMMENT '市盈率',
    c_pb         COMMENT '市净率'
) COMMENT '指数日行情' AS
SELECT
    TDATE                AS c_trade_date,
    INDEXCODE            AS c_idx_code,
    SECURITYVARIETYCODE  AS c_inner_code,
    OPEN                 AS c_open,
    HIGH                 AS c_high,
    LOW                  AS c_low,
    NEW                  AS c_close,
    LCLOSE               AS c_pre_close,
    TVOL                 AS c_volume,
    TVAL                 AS c_amount,
    PE                   AS c_pe,
    PB                   AS c_pb
FROM TYTFUND.TRAD_ID_DAILY
WHERE EISDEL = '0';
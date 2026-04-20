CREATE VIEW tytdata.tb_stk_basic_info_hk (
    c_stk_code COMMENT '证券代码',
    c_inner_code COMMENT '证券内码',
    c_company_code COMMENT '公司代码',
    c_stk_name COMMENT '证券简称',
    c_stk_type COMMENT '证券类型',
    c_trade_market COMMENT '交易市场',
    c_list_date COMMENT '上市日期',
    c_delist_date COMMENT '退市日期',
    c_list_status COMMENT '上市状态'
) COMMENT '港股基本信息表' AS
SELECT
    SECURITYCODE        AS c_stk_code,
    SECURITYVARIETYCODE AS c_inner_code,
    COMPANYCODE         AS c_company_code,
    SECURITYSHORTNAME   AS c_stk_name,
    SECURITYTYPE        AS c_stk_type,
    TRADEMARKET         AS c_trade_market,
    LISTINGDATE         AS c_list_date,
    ENDDATE             AS c_delist_date,
    CASE LISTINGSTATE
        WHEN '0'  THEN '正常上市'
        WHEN '1'  THEN '暂停上市'
        WHEN '2'  THEN '终止上市'
        WHEN '3'  THEN '恢复上市'
        WHEN '9'  THEN '未上市'
        WHEN '10' THEN '资产重组弃用'
        ELSE LISTINGSTATE
    END                 AS c_list_status
FROM TYTFUND.CDSY_SECUCODE
WHERE SECURITYTYPECODE IN (
    '058001003001',  -- H股
    '058001003002',  -- 非H股
    '058001003003'   -- 红筹股
)
  AND USESTATE = '1'
  AND EISDEL = '0'
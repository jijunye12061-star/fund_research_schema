CREATE VIEW tytdata.tb_bd_basic_info (
    c_bd_code       COMMENT '债券代码(6位)',
    c_bd_inner_code COMMENT '债券内码',
    c_bd_name       COMMENT '债券简称',
    c_bd_full_name  COMMENT '债券全称',
    c_bd_type       COMMENT '债券类型(文本,如可转换债券)',
    c_bd_type_code  COMMENT '债券类型代码',
    c_stk_code      COMMENT '正股代码(仅转债类有值)',
    c_issue_date    COMMENT '发行日',
    c_list_date     COMMENT '上市日',
    c_delist_date   COMMENT '退市日',
    c_maturity_date COMMENT '到期日',
    c_issue_vol     COMMENT '发行规模(亿元)',
    c_par_value     COMMENT '面值',
    c_coupon_rate   COMMENT '票面利率(%)',
    c_credit_rating COMMENT '信用评级',
    c_exchange      COMMENT '交易所'
) COMMENT '债券基础信息' AS
SELECT
    BONDCODE             AS c_bd_code,
    SECURITYVARIETYCODE  AS c_bd_inner_code,
    SNAME                AS c_bd_name,
    FNAME                AS c_bd_full_name,
    BONDTYPE             AS c_bd_type,
    BONDTYPECODE         AS c_bd_type_code,
    SWAPSCODE            AS c_stk_code,
    ISSUEDATE            AS c_issue_date,
    LISTDATE             AS c_list_date,
    DELISTDATE           AS c_delist_date,
    MRTYDATE             AS c_maturity_date,
    ISSUEVOL             AS c_issue_vol,
    PARVALUE             AS c_par_value,
    COUPONRATE           AS c_coupon_rate,
    CREDITRATING         AS c_credit_rating,
    TEXCH                AS c_exchange
FROM TYTFUND.BOND_BA_INFO
WHERE EISDEL = '0'

CREATE VIEW tytdata.tb_cb_analysis (
    c_trade_date          COMMENT '交易日期',
    c_bd_code             COMMENT '转债代码',
    c_bd_inner_code       COMMENT '债券内码',
    c_pure_bond_value     COMMENT '纯债价值(元)',
    c_conv_value          COMMENT '转换价值(元)',
    c_conv_prem_rate      COMMENT '转股溢价率(%)',
    c_straight_prem_rate  COMMENT '纯债溢价率(%)',
    c_floor_prem_rate     COMMENT '平底溢价率(%)',
    c_bond_value          COMMENT '转债理论价值(元)',
    c_bond_premium        COMMENT '转债溢价额(元)',
    c_bond_prem_rate      COMMENT '转债溢价率(%)',
    c_conv_delta          COMMENT '转股期权Delta',
    c_current_ytm         COMMENT '到期收益率(%)'
) COMMENT '转债估值分析' AS
SELECT
    TDATE                AS c_trade_date,
    BONDCODE             AS c_bd_code,
    SECURITYVARIETYCODE  AS c_bd_inner_code,
    PUREBONDVALUE        AS c_pure_bond_value,
    SWAPVALUE            AS c_conv_value,
    SWAPOR               AS c_conv_prem_rate,
    PUREBONDOR           AS c_straight_prem_rate,
    FLOOROR              AS c_floor_prem_rate,
    BOND_VALUE_CB        AS c_bond_value,
    BOND_PREMIUM_CB      AS c_bond_premium,
    BOND_PREMRATIO_CB    AS c_bond_prem_rate,
    SWAPD                AS c_conv_delta,
    CURRENTYTM           AS c_current_ytm
FROM TYTFUND.BOND_DR_CBANALYSIS
WHERE EISDEL = '0'

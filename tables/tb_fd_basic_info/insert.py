"""
基金基础信息表 - 数据同步
从Oracle TYTFUND同步基金基本信息

@Author: 季俊晔
@Table: tb_fd_basic_info
"""
import sys
from pathlib import Path
import pandas as pd
from utils.db_connector import OracleConnector, DorisConnector
import logging

def _setup_path():
    """兼容本地和DS环境的路径适配"""
    # 1. 本地开发：从 __file__ 向上找
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return

    # 2. DS环境：资源目录固定路径
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return

    raise RuntimeError("找不到 utils 目录，请检查路径配置")

_setup_path()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================


def _get_source_data() -> 'pd.DataFrame':
    """从Oracle获取基金基础信息"""

    sql = """
          SELECT a.c_fd_code,
                 a.c_short_name,
                 a.c_full_name,
                 a.c_estabdate,
                 a.c_terminate_date,
                 b.c_terminate_reason,
                 a.c_class1_code,
                 a.c_class1_name,
                 a.c_class2_code,
                 a.c_class2_name,
                 a.c_class3_code,
                 a.c_class3_name,
                 a.c_manager_code,
                 a.c_manager_name,
                 a.c_custodian_code,
                 a.c_custodian_name,
                 a.c_company_code,
                 a.c_company_name,
                 b.c_invest_scope,
                 b.c_invest_standard,
                 a.c_purchase_status,
                 a.c_redeem_status,
                 b.c_fund_nature,
                 b.c_transform_date,
                 CASE
                     WHEN d.FUNDCODE IS NOT NULL
                         THEN 1
                     ELSE 0
                     END as c_regular_open_status,
                 e.c_min_hold_period,
                 a.c_mgmt_fee_rate,
                 a.c_custodian_fee_rate,
                 c.c_init_code
          FROM (
                   -- 主表：基金基本信息
                   SELECT CASE
                              WHEN FCODE = '519997' THEN N'519996'
                              WHEN FCODE = '519995' THEN N'519994'
                              WHEN FCODE = '370011' THEN N'37001B'
                              ELSE FCODE
                              END   as c_fd_code,
                          SHORTNAME as c_short_name,
                          FULLNAME  as c_full_name,
                          ESTABDATE as c_estabdate,
                          TSRQ      as c_terminate_date,
                          CASE
                              WHEN FD_TYPE1 IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'007'
                              ELSE FD_TYPE1
                              END   as c_class1_code,
                          CASE
                              WHEN FD_TYPE1_NAME IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'另类投资基金'
                              ELSE FD_TYPE1_NAME
                              END   as c_class1_name,
                          CASE
                              WHEN FD_TYPE2 IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'007001'
                              ELSE FD_TYPE2
                              END   as c_class2_code,
                          CASE
                              WHEN FD_TYPE2_NAME IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'基础设施REITs'
                              ELSE FD_TYPE2_NAME
                              END   as c_class2_name,
                          CASE
                              WHEN FD_TYPE3 IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'007001001'
                              ELSE FD_TYPE3
                              END   as c_class3_code,
                          CASE
                              WHEN FD_TYPE3_NAME IS NULL AND SHORTNAME LIKE '%REIT%' THEN N'基础设施REITs'
                              ELSE FD_TYPE3_NAME
                              END   as c_class3_name,
                          JJJLID    as c_manager_code,
                          JJJL      as c_manager_name,
                          TGYHID    as c_custodian_code,
                          TGYH      as c_custodian_name,
                          JJGSID    as c_company_code,
                          JJGS      as c_company_name,
                          SGZT      as c_purchase_status,
                          SHZT      as c_redeem_status,
                          MGREXP    as c_mgmt_fee_rate,
                          TRUSTEXP  as c_custodian_fee_rate,
                          SALESEXP  as c_sales_fee_rate
                   FROM TYTFUND.FUND_JBXX
                   WHERE EISDEL = '0') a
                   LEFT JOIN (
              -- 基金概况信息
              SELECT FUNDCODE           as c_fd_code,
                     CASE
                         WHEN ENDREASON = '001' THEN '基金资产净值低于合同限制'
                         WHEN ENDREASON = '002' THEN '持有低于合同限额'
                         WHEN ENDREASON = '003' THEN '基金持有人大会同意终止'
                         WHEN ENDREASON = '004' THEN '转型终止'
                         WHEN ENDREASON = '005' THEN '合同到期终止'
                         WHEN ENDREASON = '006' THEN '其他原因'
                         WHEN ENDREASON = '007' THEN '公募转集合计划'
                         WHEN ENDREASON IS NULL THEN NULL
                         ELSE ENDREASON
                         END            as c_terminate_reason,
                     FNATURE            as c_fund_nature,
                     TO_CHAR(ISTANDARD) as c_invest_standard,
                     TO_CHAR(IRANGE)    as c_invest_scope,
                     TRANSFORM_DATE     as c_transform_date
              FROM TYTFUND.FUND_BS_OFINFO) b ON a.c_fd_code = b.c_fd_code
                   LEFT JOIN (
              -- 初始代码信息
              SELECT FUND_CODE as c_fd_code,
                     INIT_CODE as c_init_code
              FROM (SELECT FUND_CODE,
                           INIT_CODE,
                           ROW_NUMBER() OVER (PARTITION BY FUND_CODE ORDER BY REMOVE_DT DESC) as rn
                    FROM TYTFUND.DIM_FD_INIT_CODE
                    WHERE ENTRY_DT < SYSDATE
                      AND C_ISDEL = '0'
                      AND FUND_CODE NOT IN ('519997', '519995', '370011') -- 排除特殊处理的记录
                   ) t
              WHERE rn = 1

              UNION ALL

              -- 特殊映射记录
              SELECT N'519996' as c_fd_code, N'519996' as c_init_code
              FROM DUAL -- 519997 -> 519996
              UNION ALL
              SELECT N'519994' as c_fd_code, N'519994' as c_init_code
              FROM DUAL -- 519995 -> 519994
              UNION ALL
              SELECT N'37001B' as c_fd_code, N'37001B' as c_init_code
              FROM DUAL -- 370011 -> 37001B
              UNION ALL
              SELECT N'025085' as c_fd_code, N'017214' as c_init_code
              FROM DUAL -- 025085 -> 017214
              UNION ALL
              SELECT N'025936' as c_fd_code, N'003015' as c_init_code
              FROM DUAL -- 025936 -> 003015
          ) c ON a.c_fd_code = c.c_fd_code
                   LEFT JOIN (
              -- 定开基金分类信息
              SELECT DISTINCT FUNDCODE,
                              TYPECODE,
                              ISUSING,
                              ENDDATE
              FROM TYTFUND.FUND_BS_ATYPE
              WHERE TYPECODE = '105016'
                AND ISUSING = '1'
                AND ENDDATE IS NULL) d ON a.c_fd_code = d.FUNDCODE
                   LEFT JOIN (SELECT FUNDCODE AS c_fd_code,
                                     CASE
                                         WHEN CLOSE_PERIOD_UNIT = '日' THEN ROUND(CLOSEPERIOD / 30.0, 2)
                                         WHEN CLOSE_PERIOD_UNIT = '周' THEN ROUND(CLOSEPERIOD / 4.33, 2)
                                         WHEN CLOSE_PERIOD_UNIT = '月' THEN CLOSEPERIOD
                                         WHEN CLOSE_PERIOD_UNIT = '年' THEN CLOSEPERIOD * 12
                                         ELSE CLOSEPERIOD
                                         END  AS c_min_hold_period
                              FROM TYTFUND.FUND_BS_CFINFO) e on a.c_fd_code = e.c_fd_code
          """

    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql)

    df.columns = df.columns.str.lower()
    logger.info(f"从Oracle获取{len(df)}条基金基础信息")
    return df


def run(calc_date: str = None):
    """
    主入口函数 - 同步基金基础信息

    Args:
        calc_date: 计算日期（该表为全量同步，参数保留但不使用）
    """
    logger.info("=" * 60)
    logger.info(f"{calc_date}开始同步基金基础信息表")

    # 1. 获取源数据
    df = _get_source_data()
    logger.info("数据已获取完成")

    # 2. 写入Doris（全量更新）
    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_basic_info', df)

    logger.info(f"基金基础信息同步完成，共{len(df)}条记录")
    logger.info("=" * 60)


if __name__ == '__main__':
    # 测试运行
    run()
import pandas as pd
from utils.db_connector import OracleConnector, DorisConnector

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================

def _get_source_data() -> 'pd.DataFrame':
    """从Oracle获取股票基础信息"""

    sql = """
          SELECT SECURITYCODE        AS c_stk_code,
                 SECURITYVARIETYCODE AS c_inner_code,
                 COMPANYCODE         AS c_company_code,
                 SECURITYSHORTNAME   AS c_stk_name,
                 SECURITYTYPE        AS c_stk_type,
                 TRADEMARKET         AS c_trade_market,
                 LISTINGDATE         AS c_list_date,
                 ENDDATE             AS c_delist_date,
                 DECODE(LISTINGSTATE,
                        '0', N'正常上市',
                        '1', N'暂停上市',
                        '2', N'终止上市',
                        '3', N'恢复上市',
                        '9', N'未上市',
                        '10', N'资产重组弃用',
                        CAST(LISTINGSTATE AS NVARCHAR2(20))
                 )                   AS c_list_status
          FROM TYTFUND.CDSY_SECUCODE
          WHERE SECURITYTYPECODE IN (
                                     '058001003001', -- H股
                                     '058001003002', -- 非H股
                                     '058001003003' -- 红筹股
              )
            AND USESTATE = 1
            AND (EISDEL = 0 OR EISDEL IS NULL)
          """

    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql)

    df.columns = df.columns.str.lower()
    logger.info(f"从Oracle获取{len(df)}条基金基础信息")
    return df

def run():
    """
    主入口函数 - 同步股票基础信息
    """
    logger.info("=" * 60)

    # 1. 获取源数据
    df = _get_source_data()
    logger.info("数据已获取完成")

    # 2. 写入Doris（全量更新）
    with DorisConnector(ENV) as doris:
        doris.insert('tb_stk_basic_info_hk', df)

    logger.info(f"股票基础信息同步完成，共{len(df)}条记录")
    logger.info("=" * 60)


if __name__ == '__main__':
    # 测试运行
    run()
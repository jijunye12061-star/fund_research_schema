"""
港股股票行业归属表 - 静态快照
从Oracle现状表(PUBLISHSTOCK)取各分类口径最新行业代码

@Author: 季俊晔
@Table: tb_stk_industry_hk
"""
import sys
from pathlib import Path


def _setup_path():
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return
    raise RuntimeError("找不到 utils 目录，请检查路径配置")


_setup_path()

import logging
import pandas as pd
from utils.db_connector import OracleConnector, DorisConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
ENV = 'dev'
# ============================================================

# (前缀, 目标列名)
INDUSTRY_PREFIXES = [
    ('029', 'c_sw_code'),
    ('407', 'c_citic_code'),
    ('403', 'c_hkex_code'),
    ('402', 'c_gics_code'),
]


# ==================== 数据查询 ====================

def _query_hk_stocks(calc_date: str) -> pd.DataFrame:
    """获取截至calc_date已上市且未退市的港股列表"""
    sql = """
    SELECT SECURITYCODE AS c_stk_code
    FROM TYTFUND.CDSY_SECUCODE
    WHERE SECURITYTYPECODE IN ('058001003001','058001003002','058001003003')
      AND USESTATE = 1
      AND (EISDEL = 0 OR EISDEL IS NULL)
      AND ENDDATE IS NULL
      AND LISTINGDATE <= TO_DATE(:calc_date, 'YYYY-MM-DD')
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql, calc_date=calc_date)
    df.columns = df.columns.str.lower()
    return df


def _query_industry(prefix: str, code_list: list) -> pd.DataFrame:
    """查询某分类口径的现状数据, 返回(c_stk_code, code)"""
    sql = """
    SELECT SECURITYCODE AS c_stk_code,
           PUBLISHCODE  AS code
    FROM TYTFUND.CDSY_KP_PUBLISHSTOCK
    WHERE PUBLISHCODE LIKE :prefix
      AND SECURITYCODE IN (:code_list)
      AND ISENABLE = 1
      AND (EISDEL IS NULL OR EISDEL = 0)
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query_batch(sql, code_list=code_list, prefix=f'{prefix}%')
    df.columns = df.columns.str.lower()
    # 一只股票可能有多条, 取最长代码(最细粒度)
    df = df.sort_values('code').groupby('c_stk_code', as_index=False).last()
    return df


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """全量刷新港股行业归属"""
    stocks = _query_hk_stocks(calc_date)
    result = stocks.copy()
    code_list = stocks['c_stk_code'].unique().tolist()

    for prefix, col_name in INDUSTRY_PREFIXES:
        industry = _query_industry(prefix, code_list)
        industry = industry.rename(columns={'code': col_name})
        result = result.merge(industry[['c_stk_code', col_name]], on='c_stk_code', how='left')
        covered = result[col_name].notna().sum()
        logger.info(f"{col_name}({prefix}): 覆盖 {covered}/{len(result)}")

    # 至少有一个行业代码的才写入
    industry_cols = [col for _, col in INDUSTRY_PREFIXES]
    result = result.dropna(subset=industry_cols, how='all')

    with DorisConnector(ENV) as doris:
        doris.insert('tb_stk_industry_hk', result[['c_stk_code'] + industry_cols])

    logger.info(f"写入完成: {len(result)} 条")


if __name__ == '__main__':
    run('2026-03-20')
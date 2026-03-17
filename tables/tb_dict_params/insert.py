"""
行业分类字典表 - 数据同步
从Oracle TYTFUND同步各行业分类体系数据到Doris

@Table: tytdata.tb_dict_params
"""
import sys
from pathlib import Path
import pandas as pd
import logging
from utils.db_connector import OracleConnector, DorisConnector

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

QUERY_SQL = """
SELECT '002' AS c_param_type, PUBLISHCODE AS c_param_code, PUBLISHNAME AS c_param_name, PARENTCODE AS c_parent_code, '证监会行业' AS c_remark
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '002%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '002'

UNION ALL
SELECT '028', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '申万行业2021'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '028%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '028'

UNION ALL
SELECT '408', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '港股申万行业2021'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '408%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '408'

UNION ALL
SELECT '003', PUBLISHCODE, PUBLISHNAME, PARENTCODE, 'GICS行业2021'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '003%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '003'

UNION ALL
SELECT '033', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '中证行业2021'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '033%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '033'

UNION ALL
SELECT '025', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '中信行业2020'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '025%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '025'

UNION ALL
SELECT '407', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '港股中信行业2020'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '407%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '407'

UNION ALL
SELECT '403', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '港交所分类'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '403%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '403'

UNION ALL
SELECT '004', PUBLISHCODE, PUBLISHNAME, PARENTCODE, '东财分类'
FROM TYTFUND.CDSY_KP_PUBLISHRELATION
WHERE PUBLISHCODE LIKE '004%' AND ISENABLE = '1' AND EISDEL = 0 AND PUBLISHCODE != '004'
"""


def _get_source_data() -> pd.DataFrame:
    """从Oracle获取行业分类字典数据"""
    with OracleConnector(ENV) as oracle:
        df = oracle.query(QUERY_SQL)

    df.columns = df.columns.str.lower()
    logger.info(f"从Oracle获取{len(df)}条行业分类数据")
    return df


def run(calc_date: str = None):
    """
    主入口函数 - 同步行业分类字典表

    Args:
        calc_date: 计算日期（该表为全量同步，参数保留但不使用）
    """
    logger.info("=" * 60)
    logger.info(f"{calc_date}开始同步行业分类字典表")

    # 1. 获取源数据
    df = _get_source_data()
    logger.info("数据已获取完成")

    # 2. 写入Doris（全量更新）
    with DorisConnector(ENV) as doris:
        doris.insert('tb_dict_params', df)

    logger.info(f"行业分类字典同步完成，共{len(df)}条记录")
    logger.info("=" * 60)


if __name__ == '__main__':
    run()
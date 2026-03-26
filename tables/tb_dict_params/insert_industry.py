"""
行业代码字典写入 tb_dict_params
从Oracle CDSY_KP_PUBLISHRELATION读取全部行业体系

@Author: 季俊晔
@Table: tb_dict_params
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

# (前缀, c_param_type中文名)
INDUSTRY_SYSTEMS = [
    ('025', '中信行业分类'),
    ('011', '申万行业分类(旧)'),
    ('029', '申万行业分类'),
    ('033', '中证行业分类'),
    ('002', '证监会行业分类'),
    ('003', 'GICS行业分类'),
    ('403', '港交所行业分类'),
    ('402', '港股GICS行业分类'),
    ('408', '港股申万行业分类'),
    ('407', '港股中信行业分类'),
    ('004', '东财行业分类')
]


def _get_parent_code(code: str) -> str:
    """根据代码长度推导父节点"""
    if len(code) == 12:
        return code[:9]
    elif len(code) == 9:
        return code[:6]
    elif len(code) == 6:
        return code[:3]
    return ''


def _query_and_build(prefix: str, param_type: str) -> pd.DataFrame:
    """查询某体系并构造字典格式"""
    sql = """
    SELECT PUBLISHNAME AS c_param_name,
           PUBLISHCODE AS c_param_code
    FROM TYTFUND.CDSY_KP_PUBLISHRELATION
    WHERE PUBLISHCODE LIKE :prefix
        AND ISENABLE = 1
      AND (EISDEL = 0 OR EISDEL IS NULL)
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql, prefix=f'{prefix}%')

    # 只保留6/9/12位标准代码
    df.columns = df.columns.str.lower()
    df = df[df['c_param_code'].str.len().isin([3, 6, 9, 12])].copy()
    df['c_param_type'] = param_type
    df['c_parent_code'] = df['c_param_code'].apply(_get_parent_code)

    return df[['c_param_type', 'c_param_code', 'c_param_name', 'c_parent_code']]


def run():
    """写入所有行业体系的字典数据"""
    all_dfs = []
    for prefix, param_type in INDUSTRY_SYSTEMS:
        result = _query_and_build(prefix, param_type)
        all_dfs.append(result)
        logger.info(f"{param_type}: {len(result)} 条")

    combined = pd.concat(all_dfs, ignore_index=True)

    with DorisConnector(ENV) as doris:
        doris.insert('tb_dict_params', combined)

    logger.info(f"写入完成, 共 {len(combined)} 条")


if __name__ == '__main__':
    run()
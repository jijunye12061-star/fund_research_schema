"""行业分类字典同步 → tb_dict_params（11套行业体系）"""
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

import pandas as pd

from utils.db_connector import OracleConnector, DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"

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
    ('004', '东财行业分类'),
]


def _get_parent_code(code: str) -> str:
    if len(code) == 12:
        return code[:9]
    if len(code) == 9:
        return code[:6]
    if len(code) == 6:
        return code[:3]
    return ''


def run():
    sql = """
    SELECT PUBLISHCODE AS c_param_code,
           PUBLISHNAME AS c_param_name
    FROM TYTFUND.CDSY_KP_PUBLISHRELATION
    WHERE PUBLISHCODE LIKE :prefix
      AND ISENABLE = 1
      AND EISDEL = '0'
    """
    all_dfs = []
    with OracleConnector(ENV) as oracle:
        for prefix, param_type in INDUSTRY_SYSTEMS:
            df = oracle.query(sql, prefix=f'{prefix}%')
            df.columns = df.columns.str.lower()
            df = df[df['c_param_code'].str.len().isin([3, 6, 9, 12])].copy()
            df['c_param_type'] = param_type
            df['c_parent_code'] = df['c_param_code'].apply(_get_parent_code)
            df['c_remark'] = ''
            all_dfs.append(df)
            logger.info(f"{param_type}: {len(df)} 条")

    combined = pd.concat(all_dfs, ignore_index=True)[
        ['c_param_type', 'c_param_code', 'c_param_name', 'c_parent_code', 'c_remark']
    ]

    param_types_sql = ', '.join(f"'{t}'" for _, t in INDUSTRY_SYSTEMS)
    with DorisConnector(ENV) as doris:
        doris.execute(f"DELETE FROM tb_dict_params WHERE c_param_type IN ({param_types_sql})")
        doris.insert('tb_dict_params', combined)

    logger.info(f"行业分类字典同步完成，共 {len(combined)} 条")


if __name__ == '__main__':
    # ── DS 调度模式（在 tb_stk_industry 跑完后触发）──────────────────
    run()

    # ── 手动触发同上 ──────────────────────────────────────────────────
    # run()

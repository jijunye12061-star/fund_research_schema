"""概念板块字典同步 → tb_dict_params（c_param_type='概念板块'）"""
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


def run():
    sql = """
    SELECT PUBLISHCODE        AS c_param_code,
           PUBLISHNAME        AS c_param_name,
           TO_CHAR(INTRODUCE) AS c_remark
    FROM NEWSADMIN.CDSY_KP_PUBLISHINDEX
    WHERE PUBLISHCODE LIKE '007%'
      AND ISENABLE = 1
      AND EISDEL = '0'
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql)

    df.columns = df.columns.str.lower()
    df['c_param_type'] = '概念板块'
    df['c_parent_code'] = '007'
    df['c_remark'] = df['c_remark'].fillna('').str.replace(r'[\n\r\t\\"]', ' ', regex=True).str.strip()

    with DorisConnector(ENV) as doris:
        doris.execute("DELETE FROM tb_dict_params WHERE c_param_type = '概念板块'")
        doris.insert('tb_dict_params', df[
            ['c_param_type', 'c_param_code', 'c_param_name', 'c_parent_code', 'c_remark']
        ])

    logger.info(f"概念板块字典同步完成: {len(df)} 条")


if __name__ == '__main__':
    # ── DS 调度模式（在 tb_stk_concept 跑完后触发）────────────────────
    run()

    # ── 手动触发同上 ──────────────────────────────────────────────────
    # run()

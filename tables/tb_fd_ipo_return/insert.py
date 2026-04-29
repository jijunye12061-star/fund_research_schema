"""公募基金 IPO 打新收益归因 ETL

用法:
    python insert.py --init                # 全量初始化(2019+)
    python insert.py --season 2026-Q1      # 增量跑批
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

import re
import argparse
import numpy as np
import pandas as pd
from functools import partial

from utils.db_connector import OracleConnector, DorisConnector
from utils.common import get_last_quarter_end
from utils.log import setup_logger, step

from _logic import (
    LOCK_PAT,
    BOARD_PREFIXES,
    REGIME_START,
    parse_lock_ratio,
    determine_board,
    determine_regime,
)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"
logger = setup_logger(__name__)
_step = partial(step, logger)

# ==================== Constants ====================

OUTPUT_COLS = [
    'c_fd_code', 'c_init_code', 'c_stk_code', 'c_stk_inner_code',
    'c_finance_code', 'c_board', 'c_regime', 'c_list_date', 'c_sell_date',
    'c_issue_price', 'c_sell_vwap', 'c_confirmed_return',
    'c_alloc_qty_total', 'c_lock_ratio', 'c_alloc_qty_unlocked',
    'c_pnl_unlocked', 'c_net_asset_estimate', 'c_net_asset_report_date',
    'c_size_method',
]

DATA_START = '2019-01-01'

# ==================== Query Functions ====================


def _query_ipo_placement(
    oracle: OracleConnector,
    start_date: str,
    end_date: str = '2099-12-31',
) -> pd.DataFrame:
    """从 Oracle 拉取 IPO 配售明细（按 NOTICEDATE 过滤）

    Returns:
        DataFrame with columns:
        c_finance_code, c_issue_price, c_stk_inner_code,
        c_fd_code, c_alloc_qty_total, lock_text
    """
    sql = """
    SELECT
        i.FINANCECODE            AS c_finance_code,
        i.ISSUEPRICE             AS c_issue_price,
        i.SECURITY_INNER_CODE    AS c_stk_inner_code,
        p.PLACING_OBJECT_CODE    AS c_fd_code,
        SUM(p.SHAREPLACE)        AS c_alloc_qty_total,
        MAX(p.LOCKPERIOD)        AS lock_text
    FROM TYTFUND.CPI_ISSUEBASICINFO i
    JOIN TYTFUND.CPI_PLACERESULT p
      ON p.FINANCECODE = i.FINANCECODE
    WHERE i.SECURITYTYPECODE = '058001001'
      AND i.FINATYPE = '001'
      AND p.PLACEOBJECTTYPE = '网下机构投资者'
      AND p.PLACING_OBJECT_CODE IS NOT NULL
      AND i.NOTICEDATE >= :start_date
      AND i.NOTICEDATE <= :end_date
    GROUP BY i.FINANCECODE, i.ISSUEPRICE, i.SECURITY_INNER_CODE,
             p.PLACING_OBJECT_CODE
    """
    return oracle.query(sql, start_date=start_date, end_date=end_date)


def _query_stk_info(
    doris: DorisConnector, inner_codes: list[int],
) -> pd.DataFrame:
    """通过内码关联获取股票代码和上市日"""
    sql = """
    SELECT c_inner_code AS c_stk_inner_code,
           c_stk_code,
           c_list_date
    FROM tytdata.tb_stk_basic_info
    WHERE c_inner_code IN (:code_list)
    """
    return doris.query_batch(sql, code_list=inner_codes)


def _query_init_code_map(
    doris: DorisConnector, fd_codes: list[str],
) -> pd.DataFrame:
    """基金子份额 → 主代码映射（同时过滤掉非公募基金）"""
    sql = """
    SELECT c_fd_code, c_init_code
    FROM tytdata.tb_fd_basic_info
    WHERE c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, code_list=fd_codes)


# ==================== Processing Functions ====================


def _enrich_and_apply_rules(
    raw: pd.DataFrame,
    doris: DorisConnector,
) -> pd.DataFrame:
    """关联股票信息 → 过滤公募 → 判定板块/制度/锁定比例"""
    inner_codes = raw['c_stk_inner_code'].unique().tolist()

    with _step("Doris: 关联股票信息"):
        stk_info = _query_stk_info(doris, inner_codes)
    df = raw.merge(stk_info, on='c_stk_inner_code', how='inner')

    # 过滤: 只保留 2019+ 上市的 IPO
    df['c_list_date'] = pd.to_datetime(df['c_list_date'])
    df = df[df['c_list_date'] >= DATA_START].copy()
    if df.empty:
        return df

    with _step("Doris: 匹配主代码(过滤非公募)"):
        init_map = _query_init_code_map(doris, df['c_fd_code'].unique().tolist())
    df = df.merge(init_map, on='c_fd_code', how='inner')
    logger.info(f"  公募基金命中 {len(df)} 行 / 原始 {len(raw)} 行")

    with _step("判定板块/制度/锁定比例"):
        df['c_stk_code'] = df['c_stk_code'].astype(str)
        df['c_board'] = df['c_stk_code'].apply(determine_board)
        list_date_str = df['c_list_date'].dt.strftime('%Y-%m-%d')
        df['c_regime'] = [
            determine_regime(b, d)
            for b, d in zip(df['c_board'], list_date_str)
        ]
        df['c_lock_ratio'] = df['lock_text'].apply(parse_lock_ratio)
        df['c_alloc_qty_unlocked'] = (
            df['c_alloc_qty_total'] * (1 - df['c_lock_ratio'])
        )

    df.drop(columns=['lock_text'], inplace=True)
    return df


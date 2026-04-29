# tables/tb_fd_ipo_return/insert.py
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

# 延迟导入 utils 到实际使用时，以支持单测
try:
    from utils.db_connector import OracleConnector, DorisConnector
    from utils.common import get_last_quarter_end
    from utils.log import setup_logger, step
    _env = "${db_env}"
    ENV = _env if not _env.startswith("${") else "dev"
    logger = setup_logger(__name__)
    _step = partial(step, logger)
except (ImportError, Exception) as e:
    # 单测或本地开发环境下，允许 utils 导入失败
    logger = None
    _step = None
    ENV = "dev"

# ==================== Constants ====================

LOCK_PAT = re.compile(r'(\d{1,3})\s*%[^,。;]{0,8}股份[^,。;]{0,4}[锁限]')

BOARD_PREFIXES = [
    (['688', '689'], 'star'),
    (['300', '301'], 'gem'),
    (['60'], 'main_sh'),
    (['000', '001', '002', '003'], 'main_sz'),
    (['83', '87', '92'], 'bse'),
]

REGIME_START = {
    'star': '2019-07-22',
    'gem': '2020-08-24',
    'main_sh': '2023-04-10',
    'main_sz': '2023-04-10',
    'bse': '2021-11-15',
}

OUTPUT_COLS = [
    'c_fd_code', 'c_init_code', 'c_stk_code', 'c_stk_inner_code',
    'c_finance_code', 'c_board', 'c_regime', 'c_list_date', 'c_sell_date',
    'c_issue_price', 'c_sell_vwap', 'c_confirmed_return',
    'c_alloc_qty_total', 'c_lock_ratio', 'c_alloc_qty_unlocked',
    'c_pnl_unlocked', 'c_net_asset_estimate', 'c_net_asset_report_date',
    'c_size_method',
]

DATA_START = '2019-01-01'

# ==================== Pure Functions ====================


def parse_lock_ratio(text: str) -> float:
    if not text:
        return 0.0
    m = LOCK_PAT.search(text)
    return int(m.group(1)) / 100 if m else 0.0


def determine_board(stk_code: str) -> str:
    for prefixes, board in BOARD_PREFIXES:
        if any(stk_code.startswith(p) for p in prefixes):
            return board
    return 'unknown'


def determine_regime(board: str, list_date: str) -> str:
    start = REGIME_START.get(board)
    if start is None:
        return 'unknown'
    return 'registration' if list_date >= start else 'approval'

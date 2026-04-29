"""tb_fd_ipo_return 纯逻辑模块 — 不依赖 utils/数据库，便于单测。"""
import re

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

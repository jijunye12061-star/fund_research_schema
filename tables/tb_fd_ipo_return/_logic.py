"""tb_fd_ipo_return 纯逻辑模块 — 不依赖 utils/数据库，便于单测。"""
import re

# 拆句标点（中英文逗号/句号/分号）
_SENT_SPLIT = re.compile(r'[,，。；;]')

# 句中百分比（X% / X %）
_PCT_PAT = re.compile(r'(\d{1,3})\s*%')

# 否定描述（描述"未锁定"部分），命中则跳过该句
_NEG_KEYWORDS = ('无限售', '不限售', '无锁定', '不锁定', '无锁', '无限制', '无流通限制')

# 肯定描述（描述真正锁定部分）
_POS_KEYWORDS = ('限售', '锁定', '限制')


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
    """从 LOCKPERIOD 文本提取锁定比例。

    策略：按标点拆句，跳过"无锁定/不限售"等否定句，
    在含"限售/锁定/限制"的肯定句中取百分号数字。

    例：
        "90%的股份无限售期, 10%的股份限售期为6个月"
        → 跳过第一句, 第二句匹配 10 → 0.10
    """
    if not text:
        return 0.0
    for sent in _SENT_SPLIT.split(text):
        if any(neg in sent for neg in _NEG_KEYWORDS):
            continue
        if not any(pos in sent for pos in _POS_KEYWORDS):
            continue
        m = _PCT_PAT.search(sent)
        if m:
            return int(m.group(1)) / 100
    return 0.0


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

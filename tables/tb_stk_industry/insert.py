"""
A股股票行业归属表 - 日频快照
每日从Oracle读取行业事件, 生成当日所有A股的行业归属

申万新旧切换: 2021-07-30前用011, 之后用029

@Author: 季俊晔
@Table: tb_stk_industry
"""
import sys
from pathlib import Path


def _setup_path():
    """兼容本地和DS环境的路径适配"""
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
from typing import List

import pandas as pd

from utils.db_connector import OracleConnector, DorisConnector
from utils.common import get_trade_calendar

from utils.log import setup_logger
logger = setup_logger(__name__)

# ============================================================
_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"  # 调度注入db_env参数；本地默认dev
# ============================================================

CITIC_PREFIX = '025'
SW_OLD_PREFIX = '011'
SW_NEW_PREFIX = '029'
SW_SWITCH_DATE = '2021-07-30'
CODE_LEN = 12


# ==================== 数据查询 ====================

def _query_events(end_date: str) -> pd.DataFrame:
    """查询截至end_date的全量行业I事件"""
    sql = """
    SELECT SECURITYCODE AS c_stk_code,
           OPDATE       AS c_change_date,
           PUBLISHCODE  AS c_industry_code
    FROM TYTFUND.CDSY_KP_PUBLISHHISSTOCK
    WHERE (PUBLISHCODE LIKE '025%'
        OR PUBLISHCODE LIKE '011%'
        OR PUBLISHCODE LIKE '029%')
      AND TYPE = 'I'
      AND OPDATE <= TO_DATE(:end_date, 'YYYY-MM-DD')
        AND (EISDEL = 0 OR EISDEL IS NULL)
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql, end_date=end_date)

    df.columns = df.columns.str.lower()
    df['c_change_date'] = pd.to_datetime(df['c_change_date'])
    logger.info(f"查询到 {len(df)} 条行业事件")
    return df


def _get_stock_list(trade_date: str) -> List[str]:
    """获取指定日期的A股存续股票列表"""
    sql = """
    SELECT c_stk_code
    FROM tytdata.tb_stk_basic_info
    WHERE c_list_date <= :trade_date
      AND (c_delist_date IS NULL OR c_delist_date > :trade_date)
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, trade_date=trade_date)
    return df['c_stk_code'].tolist()


# ==================== 核心逻辑 ====================

def _latest_assignment(
    events: pd.DataFrame,
    target_date: pd.Timestamp,
    stocks: List[str],
    prefix: str
) -> pd.Series:
    """取每只股票截至target_date最近一次I事件的行业代码"""
    mask = (
        events['c_industry_code'].str.startswith(prefix)
        & (events['c_industry_code'].str.len() == CODE_LEN)
        & (events['c_change_date'] <= target_date)
        & events['c_stk_code'].isin(stocks)
    )
    filtered = events.loc[mask].sort_values('c_change_date')
    return filtered.groupby('c_stk_code')['c_industry_code'].last()


def _get_snapshot(
    events: pd.DataFrame,
    trade_date: str,
    stocks: List[str]
) -> pd.DataFrame:
    """生成某交易日的行业归属快照"""
    td = pd.Timestamp(trade_date)

    # 中信
    citic = _latest_assignment(events, td, stocks, CITIC_PREFIX)
    citic.name = 'c_citic_code'

    # 申万: 按日期选新旧
    sw_prefix = SW_NEW_PREFIX if td >= pd.Timestamp(SW_SWITCH_DATE) else SW_OLD_PREFIX
    sw = _latest_assignment(events, td, stocks, sw_prefix)
    sw.name = 'c_sw_code'

    # 合并
    result = pd.DataFrame({'c_stk_code': stocks})
    result = result.join(citic, on='c_stk_code')
    result = result.join(sw, on='c_stk_code')
    result['c_trade_date'] = trade_date

    result = result.dropna(subset=['c_citic_code', 'c_sw_code'], how='all')
    return result[['c_trade_date', 'c_stk_code', 'c_citic_code', 'c_sw_code']]


# ==================== 主入口 ====================

def run(calc_date: str, events: pd.DataFrame = None) -> None:
    """日增量: 处理calc_date当天

    Args:
        calc_date: 执行日期, 如 '2026-03-17'
        events: 行业变动信息
    """
    if events is None:
        events = _query_events(calc_date)
    events = events[events['c_change_date'] <= calc_date]
    trade_dates = get_trade_calendar(calc_date, calc_date)
    if trade_dates.empty:
        logger.debug(f"{calc_date} 非交易日, 跳过")
        return

    logger.info(f"开始处理 {calc_date}")

    stocks = _get_stock_list(calc_date)
    result = _get_snapshot(events, calc_date, stocks)

    with DorisConnector(ENV) as doris:
        doris.insert('tb_stk_industry', result)

    logger.info(f"完成 {calc_date}: {len(result)} 条")


if __name__ == '__main__':
    # ── DS 调度模式 ──────────────────────────────────────────────────
    raw = "$[yyyyMMdd-1]"
    run(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）────────────────
    # main_events = _query_events('2026-03-17')
    # for dt in get_trade_calendar('2015-01-01', '2026-03-17'):
    #     run(dt.strftime('%Y-%m-%d'), main_events)
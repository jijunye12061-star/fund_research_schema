"""
A股股票概念归属表 - 日频快照
从Oracle行业事件表读取概念调入/调出事件, 生成当日概念归属

与tb_stk_industry区别: 一股多概念, 需处理D(移出)事件

@Author: 季俊晔
@Table: tb_stk_concept
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

CONCEPT_PREFIX = '007'


# ==================== 数据查询 ====================

def _query_events(end_date: str) -> pd.DataFrame:
    """查询截至end_date的全量概念I/D事件"""
    sql = """
    SELECT SECURITYCODE AS c_stk_code,
           OPDATE       AS c_change_date,
           PUBLISHCODE  AS c_concept_code,
           TYPE         AS c_type
    FROM TYTFUND.CDSY_KP_PUBLISHHISSTOCK
    WHERE PUBLISHCODE LIKE '007%'
      AND TYPE IN ('I', 'D')
      AND OPDATE <= TO_DATE(:end_date, 'YYYY-MM-DD')
      AND (EISDEL = 0 OR EISDEL IS NULL)
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql, end_date=end_date)

    df.columns = df.columns.str.lower()
    df['c_change_date'] = pd.to_datetime(df['c_change_date'])
    logger.info(f"查询到 {len(df)} 条概念事件")
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

def _get_snapshot(
    events: pd.DataFrame,
    trade_date: str,
    stocks: List[str]
) -> pd.DataFrame:
    """生成某交易日的概念归属快照

    对每个(股票, 概念)取最近一条事件:
    - 最近是I → 属于该概念
    - 最近是D → 不属于该概念
    """
    td = pd.Timestamp(trade_date)
    mask = (
        (events['c_change_date'] <= td)
        & events['c_stk_code'].isin(stocks)
    )
    filtered = events.loc[mask].sort_values('c_change_date')

    # 每个(股票, 概念)取最后一条事件
    latest = filtered.groupby(['c_stk_code', 'c_concept_code']).last()

    # 仅保留最后事件为I(调入)的
    active = latest[latest['c_type'] == 'I'].reset_index()

    active['c_trade_date'] = trade_date
    return active[['c_trade_date', 'c_stk_code', 'c_concept_code']]


# ==================== 字典同步 ====================

def sync_dict() -> None:
    """同步概念板块字典到tb_dict_params"""
    sql = """
    SELECT PUBLISHCODE  AS c_param_code,
           PUBLISHNAME  AS c_param_name,
           INTRODUCE    AS c_remark
    FROM NEWSADMIN.CDSY_KP_PUBLISHINDEX
    WHERE PUBLISHCODE LIKE '007%'
      AND ISENABLE = 1
    """
    with OracleConnector(ENV) as oracle:
        df = oracle.query(sql)

    df.columns = df.columns.str.lower()
    df['c_param_type'] = '概念板块'
    df['c_parent_code'] = '007'

    with DorisConnector(ENV) as doris:
        doris.execute(
            "DELETE FROM tb_dict_params WHERE c_param_type = '概念板块'"
        )
        doris.insert('tb_dict_params', df[
            ['c_param_type', 'c_param_code', 'c_param_name',
             'c_parent_code', 'c_remark']
        ])

    logger.info(f"概念字典同步完成: {len(df)} 条")


# ==================== 主入口 ====================

def run(calc_date: str, events: pd.DataFrame = None) -> None:
    """日增量: 处理calc_date当天"""
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
        doris.insert('tb_stk_concept', result)

    logger.info(f"完成 {calc_date}: {len(result)} 条")


if __name__ == '__main__':
    # ── DS 调度模式 ──────────────────────────────────────────────────
    raw = "$[yyyyMMdd-1]"
    run(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）────────────────
    # main_events = _query_events('2026-04-09')
    # for dt in get_trade_calendar('2015-01-05', '2026-04-09'):
    #     run(dt.strftime('%Y-%m-%d'), main_events)
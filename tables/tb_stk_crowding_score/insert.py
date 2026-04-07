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
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ENV = 'dev'

OUTPUT_COLS = [
    'c_report_date', 'c_stk_code',
    'c_total_hold_mv', 'c_crowd_score_mkt',
]


# ==================== 数据查询 ====================

def _get_equity_funds(doris: DorisConnector, report_date: str) -> list[str]:
    """广义权益基金：001(权益基金) + 004(混合型基金)"""
    sql = """
    SELECT DISTINCT c_fd_code FROM tytdata.tb_fd_category
    WHERE c_type1_code IN ('001', '004')
      AND c_report_date = :report_date
    """
    return doris.query(sql, report_date=report_date)['c_fd_code'].tolist()


def _query_full_holdings(doris: DorisConnector, fund_codes: list[str],
                         report_date: str) -> pd.DataFrame:
    """查询全持仓（半年报 c_style IN ('02','04')），去重后取最大市值"""
    sql = """
    SELECT c_fd_code, c_stk_code, MAX(c_hold_value) AS c_hold_value
    FROM tytdata.tb_fd_portfolio_stk
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style IN ('02', '04')
      AND c_hold_value > 0
      AND LENGTH(c_stk_code) = 6
    GROUP BY c_fd_code, c_stk_code
    """
    return doris.query_batch(sql, code_list=fund_codes, report_date=report_date)


# ==================== 计算 ====================

def _calc_market_crowding(holdings: pd.DataFrame) -> pd.DataFrame:
    """按股票聚合全市场权益基金持仓市值，计算百分位排名"""
    agg = (holdings.groupby('c_stk_code')['c_hold_value']
           .sum()
           .rename('c_total_hold_mv')
           .reset_index())
    agg['c_crowd_score_mkt'] = agg['c_total_hold_mv'].rank(pct=True, method='average').round(4)
    return agg


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date 须为半年报期：'2024-06-30' 或 '2024-12-31'"""
    assert calc_date[5:] in ('06-30', '12-31'), "calc_date 必须为半年报期"
    logger.info(f"计算 {calc_date}")

    with DorisConnector(ENV) as doris:
        fund_codes = _get_equity_funds(doris, calc_date)
        logger.info(f"广义权益基金 {len(fund_codes)} 只")

        holdings = _query_full_holdings(doris, fund_codes, calc_date)
        logger.info(f"持仓记录: {len(holdings)}")

        result = _calc_market_crowding(holdings)
        result['c_report_date'] = pd.to_datetime(calc_date)
        doris.insert('tb_stk_crowding_score', result[OUTPUT_COLS])

    logger.info(f"写入完成 {calc_date}: {len(result)} 条")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        run(f'{raw[:4]}-{raw[4:6]}-{raw[6:]}')
    else:
        # 历史补数：近 20 个半年报期
        semi_dates = [d for d in generate_report_dates('2025-12-31', 40)
                      if d[5:] in ('06-30', '12-31')]
        for dt in semi_dates:
            run(dt)

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
from utils.common import generate_report_dates

from utils.log import setup_logger
logger = setup_logger(__name__)

ENV = 'dev'

OUTPUT_COLS = [
    'c_report_date', 'c_fd_code',
    'c_buy_amount', 'c_sell_amount',
    'c_avg_stk_mv', 'c_turnover_rate',
]


# ==================== 辅助 ====================

def _semi_annual_dates(calc_date: str, n: int) -> list[str]:
    """最近 n 个半年报期（含 calc_date 当期，仅 06-30/12-31）"""
    return [d for d in generate_report_dates(calc_date, n * 2)
            if d[5:] in ('06-30', '12-31')][:n]


def _denom_dates(calc_date: str) -> tuple[str, str, str]:
    """换手率分母所需的三个季度末日期"""
    year = int(calc_date[:4])
    if calc_date[5:] == '06-30':
        return f'{year - 1}-12-31', f'{year}-03-31', f'{year}-06-30'
    else:
        return f'{year}-06-30', f'{year}-09-30', f'{year}-12-31'


# ==================== 数据查询 ====================

def _query_trade_sum(oracle: OracleConnector, year: int) -> pd.DataFrame:
    """查询指定年度所有基金的买入/卖出金额（STYLE 02=中报/04=年报）"""
    sql = """
    SELECT FUNDCODE, STYLE, SHARECOST, SELLSUM
    FROM TYTFUND.FUND_IV_STOCKTRADESUM
    WHERE EXTRACT(YEAR FROM ENDDATE) = :year
      AND STYLE IN ('02', '04')
      AND EISDEL = '0'
    """
    return oracle.query(sql, year=year)


def _query_stk_mv(doris: DorisConnector, d0: str, d1: str, d2: str) -> pd.DataFrame:
    """查询三期季度末股票投资市值（c_stk_total_mv = SIMVSUM）"""
    sql = """
    SELECT c_fd_code, c_report_date, MAX(c_stk_total_mv) AS c_stk_total_mv
    FROM tytdata.tb_fd_asset_allocation
    WHERE c_report_date IN (:d0, :d1, :d2)
      AND c_style IN ('01', '02', '03', '04')
    GROUP BY c_fd_code, c_report_date
    """
    return doris.query(sql, d0=d0, d1=d1, d2=d2)


# ==================== 计算 ====================

def _calc_turnover(trade_df: pd.DataFrame, mv_df: pd.DataFrame,
                   calc_date: str) -> pd.DataFrame:
    """计算半年度双边换手率"""
    year = int(calc_date[:4])
    is_h1 = calc_date[5:] == '06-30'
    d0, d1, d2 = _denom_dates(calc_date)

    # 买卖金额 - 先聚合，防止基金变动时同FUNDCODE存在多段记录
    if is_h1:
        biz = (trade_df[trade_df['STYLE'] == '02']
               .groupby('FUNDCODE')[['SHARECOST', 'SELLSUM']].sum()
               .reset_index())
    else:
        full = (trade_df[trade_df['STYLE'] == '04']
                .groupby('FUNDCODE')[['SHARECOST', 'SELLSUM']].sum()
                .reset_index())
        h1 = (trade_df[trade_df['STYLE'] == '02']
              .groupby('FUNDCODE')[['SHARECOST', 'SELLSUM']].sum()
              .reset_index())
        biz = full.merge(h1, on='FUNDCODE', suffixes=('_full', '_h1'))
        biz['SHARECOST'] = biz['SHARECOST_full'] - biz['SHARECOST_h1']
        biz['SELLSUM'] = biz['SELLSUM_full'] - biz['SELLSUM_h1']
        biz = biz[['FUNDCODE', 'SHARECOST', 'SELLSUM']]

    # 三期均值
    pivot = mv_df.pivot(index='c_fd_code', columns='c_report_date', values='c_stk_total_mv')
    pivot.columns = [str(c)[:10] for c in pivot.columns]
    pivot['c_avg_stk_mv'] = pivot[[d0, d1, d2]].mean(axis=1)
    avg_mv = pivot[['c_avg_stk_mv']].reset_index()

    biz['SHARECOST'] = biz['SHARECOST'].fillna(0)
    biz['SELLSUM'] = biz['SELLSUM'].fillna(0)

    result = biz.rename(columns={
        'FUNDCODE': 'c_fd_code',
        'SHARECOST': 'c_buy_amount',
        'SELLSUM': 'c_sell_amount',
    }).merge(avg_mv, on='c_fd_code', how='inner')

    result['c_turnover_rate'] = (
        (result['c_buy_amount'] + result['c_sell_amount']) / result['c_avg_stk_mv'] * 100
    ).round(4)
    # 分母为0或市值极小（<100万）：过渡态基金，换手率无业务含义
    result.loc[result['c_avg_stk_mv'] < 1_000_000, 'c_turnover_rate'] = None
    result['c_report_date'] = pd.to_datetime(calc_date)
    return result


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date 须为半年报期：'2024-06-30' 或 '2024-12-31'"""
    assert calc_date[5:] in ('06-30', '12-31'), "calc_date 必须为半年报期"
    year = int(calc_date[:4])
    d0, d1, d2 = _denom_dates(calc_date)
    logger.info(f"计算 {calc_date}，分母日期: {d0}, {d1}, {d2}")

    with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
        trade_df = _query_trade_sum(oracle, year)
        mv_df = _query_stk_mv(doris, d0, d1, d2)
        logger.info(f"Oracle 交易记录: {len(trade_df)}，Doris 市值记录: {len(mv_df)}")

        result = _calc_turnover(trade_df, mv_df, calc_date)
        doris.insert('tb_fd_turnover', result[OUTPUT_COLS])

    logger.info(f"写入完成 {calc_date}: {len(result)} 条")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        run(f'{raw[:4]}-{raw[4:6]}-{raw[6:]}')
    else:
        # 历史补数：从 2015-12-31 起（项目数据起点）到最新期
        start = '2015-12-31'
        all_dates = _semi_annual_dates('2025-12-31', 40)  # 40期覆盖20年
        for dt in [d for d in all_dates if d >= start]:
            run(dt)

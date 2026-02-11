"""
基金绝对收益指标表 - 数据计算
计算基金在不同时间区间的绝对收益表现指标

关键设计：
- 年化收益率：期初期末净值法，自然日（365）
- 年化波动率：交易日收益率，sqrt(252) 标准年化
- 数据来源：Doris tb_fd_nav_daily（纯交易日记录，无需 trade_dates 过滤）

@Author: 季俊晔
@Table: tb_fd_perform_abs
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta

sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.db_connector import DorisConnector
from utils.common import get_trade_calendar, get_active_funds, safe_divide

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
ENV = 'prod'  # 切换环境: 'dev' | 'prod'
# ============================================================

# ==================== 配置 ====================

@dataclass
class PeriodConfig:
    code: str
    name: str
    months: Optional[int] = None
    years: Optional[int] = None
    type: str = 'fixed'  # fixed / ytd / si


PERIOD_CONFIGS = [
    PeriodConfig('00', '近1月',  months=1,  type='fixed'),
    PeriodConfig('01', '近3月',  months=3,  type='fixed'),
    PeriodConfig('02', '近6月',  months=6,  type='fixed'),
    PeriodConfig('03', '近1年',  years=1,   type='fixed'),
    PeriodConfig('04', '近2年',  years=2,   type='fixed'),
    PeriodConfig('05', '近3年',  years=3,   type='fixed'),
    PeriodConfig('06', '近5年',  years=5,   type='fixed'),
    PeriodConfig('07', '今年来', type='ytd'),
    PeriodConfig('08', '成立来', type='si'),
]

RF_RATE = 0.02               # 无风险年化收益率
NATURAL_DAYS_PER_YEAR = 365
TRADING_DAYS_PER_YEAR = 252
MIN_TRADE_DAYS = 21          # 区间内最少交易日数，不足则跳过
BATCH_SIZE = 100


@dataclass
class PeriodCalcInfo:
    config: PeriodConfig
    start_date: datetime


# ==================== 数据获取 ====================

def _get_nav_data(fund_codes: List[str], calc_date: str) -> pd.DataFrame:
    """从 Doris 批量获取净值数据（仅含交易日记录）"""
    sql = """
    SELECT c_fd_code, c_trade_date, c_nav_adj, c_ret_1d
    FROM tytdata.tb_fd_nav_daily
    WHERE c_fd_code IN (:code_list)
      AND c_trade_date <= :calc_date
        AND c_is_trade = 1
    """
    with DorisConnector(ENV) as doris:
        df = doris.query_batch(sql, fund_codes, calc_date=calc_date)

    df['c_trade_date'] = pd.to_datetime(df['c_trade_date'])
    df['c_nav_adj'] = pd.to_numeric(df['c_nav_adj'], errors='coerce')
    df['c_ret_1d'] = pd.to_numeric(df['c_ret_1d'], errors='coerce')
    return df


# ==================== 区间判断 ====================

def _get_period_start(calc_date: datetime, period: PeriodConfig, estab_date: datetime) -> datetime:
    """计算区间起始日期"""
    if period.type == 'fixed':
        delta = relativedelta(months=period.months) if period.months else relativedelta(years=period.years)
        return calc_date - delta
    if period.type == 'ytd':
        return datetime(calc_date.year, 1, 1)
    if period.type == 'si':
        return estab_date
    raise ValueError(f"未知区间类型: {period.type}")


def _get_valid_periods(estab_date: datetime, calc_date: datetime) -> List[PeriodCalcInfo]:
    """返回该基金在 calc_date 上有效的区间列表"""
    valid = []
    for period in PERIOD_CONFIGS:
        start_date = _get_period_start(calc_date, period, estab_date)
        # si 区间无条件有效；其余要求成立日 <= 区间起始
        if period.type == 'si' or estab_date <= start_date:
            valid.append(PeriodCalcInfo(config=period, start_date=start_date))
    return valid


# ==================== 指标计算 ====================

def _ann_vol(returns: pd.Series) -> Optional[float]:
    """年化波动率(%)，传入不同的 returns 切片即可得上行/下行/总体"""
    if len(returns) < 2:
        return None
    return returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100


def _calc_period_return(nav: pd.Series) -> float:
    """区间总收益率(%)"""
    return (nav.iloc[-1] / nav.iloc[0] - 1) * 100


def _calc_ann_return(nav: pd.Series, natural_days: int) -> Optional[float]:
    """年化收益率(%) - 期初期末净值法，自然日年化"""
    total_ret = nav.iloc[-1] / nav.iloc[0] - 1
    if total_ret <= -1:
        return None
    return ((1 + total_ret) ** (NATURAL_DAYS_PER_YEAR / natural_days) - 1) * 100


def _calc_max_drawdown(nav: pd.Series) -> float:
    """最大回撤(%) - 正数表示"""
    return abs((nav / nav.cummax() - 1).min()) * 100


def _calc_sharpe(returns: pd.Series) -> Optional[float]:
    """夏普比率"""
    daily_rf = RF_RATE / TRADING_DAYS_PER_YEAR
    excess = returns - daily_rf
    return safe_divide(
        excess.mean() * np.sqrt(TRADING_DAYS_PER_YEAR),
        excess.std(),
        default=None, min_denominator=1e-8, max_result=100
    )


def _calc_calmar(nav: pd.Series, natural_days: int) -> Optional[float]:
    """卡玛比率 = 年化收益率 / 最大回撤（期初期末净值法）"""
    ann_ret = _calc_ann_return(nav, natural_days)
    mdd = _calc_max_drawdown(nav)
    if ann_ret is None:
        return None
    return safe_divide(ann_ret / 100, mdd / 100, default=None, min_denominator=1e-6, max_result=100)


def _calc_sortino(returns: pd.Series) -> Optional[float]:
    """索提诺比率"""
    daily_rf = RF_RATE / TRADING_DAYS_PER_YEAR
    excess = returns - daily_rf
    downside_std = excess[excess < 0].std()
    return safe_divide(
        excess.mean() * np.sqrt(TRADING_DAYS_PER_YEAR),
        downside_std,
        default=None, min_denominator=1e-8, max_result=100
    )


def _calc_metrics(nav: pd.Series, returns: pd.Series, natural_days: int) -> Dict:
    """计算单区间所有指标，数据不足时返回空 dict"""
    if len(returns) < MIN_TRADE_DAYS:
        return {}

    mdd = _calc_max_drawdown(nav)

    return {
        'c_period_ret':    _calc_period_return(nav),
        'c_ann_ret':       _calc_ann_return(nav, natural_days),
        'c_ann_vol':       _ann_vol(returns),
        'c_up_side_vol':   _ann_vol(returns[returns > 0]),
        'c_down_side_vol': _ann_vol(returns[returns < 0]),
        'c_mdd':           mdd,
        'c_sharpe':        _calc_sharpe(returns),
        'c_calmar':        _calc_calmar(nav, natural_days),
        'c_sortino':       _calc_sortino(returns),
        'c_skewness':      returns.skew()     if len(returns) >= 3 else None,
        'c_kurtosis':      returns.kurtosis() if len(returns) >= 4 else None,
        'c_break_ratio':   (nav >= nav.cummax()).sum() / len(nav) * 100,
    }


# ==================== 单只基金处理 ====================

def _calc_fund_metrics(
        fund_code: str,
        calc_date: datetime,
        nav_df: pd.DataFrame,
        estab_date: datetime,
) -> List[Dict]:
    """计算单只基金所有有效区间的指标"""
    nav_df = nav_df.sort_values('c_trade_date')

    # 计算日无净值则跳过（该日可能停牌或数据缺失）
    if calc_date not in nav_df['c_trade_date'].values:
        logger.warning(f"{fund_code} 在 {calc_date.date()} 无净值，跳过")
        return []

    results = []
    for period_info in _get_valid_periods(estab_date, calc_date):
        period_df = nav_df[
            (nav_df['c_trade_date'] >= period_info.start_date) &
            (nav_df['c_trade_date'] <= calc_date)
        ]
        if len(period_df) < 2:
            continue

        nav = period_df['c_nav_adj']
        returns = period_df['c_ret_1d'].dropna()
        natural_days = (period_df['c_trade_date'].iloc[-1] - period_df['c_trade_date'].iloc[0]).days

        metrics = _calc_metrics(nav, returns, natural_days)
        if not metrics:
            continue

        results.append({
            'c_fd_code':     fund_code,
            'c_trade_date':  calc_date.date(),
            'c_period_code': period_info.config.code,
            **metrics
        })

    return results


# ==================== 批量处理 ====================

def _process_batch(fund_batch: pd.DataFrame, calc_date: datetime) -> pd.DataFrame:
    """处理一批基金，拉取净值后逐只计算"""
    fund_codes = fund_batch['c_fd_code'].tolist()
    nav_df = _get_nav_data(fund_codes, calc_date.strftime('%Y-%m-%d'))

    if nav_df.empty:
        logger.warning(f"本批 {len(fund_codes)} 只基金无净值数据")
        return pd.DataFrame()

    all_results = []
    for _, fund_info in fund_batch.iterrows():
        fund_code = fund_info['c_fd_code']
        fund_nav = nav_df[nav_df['c_fd_code'] == fund_code]
        if fund_nav.empty:
            continue

        fund_results = _calc_fund_metrics(
            fund_code,
            calc_date,
            fund_nav,
            pd.to_datetime(fund_info['c_estabdate']),
        )
        all_results.extend(fund_results)

    if not all_results:
        return pd.DataFrame()

    result_df = pd.DataFrame(all_results)
    logger.info(f"本批生成 {len(result_df)} 条指标")
    return result_df


# ==================== 主函数 ====================

def run(calc_date: str):
    """主入口 - 计算指定日期所有存续基金的绝对收益指标"""
    logger.info("=" * 60)
    logger.info(f"开始计算 {calc_date} 的基金业绩指标")

    calc_date_dt = datetime.strptime(calc_date, '%Y-%m-%d')

    # 非交易日跳过（取单日历即可，不需要完整日历）
    trade_dates = get_trade_calendar(calc_date, calc_date)
    if calc_date_dt not in trade_dates:
        logger.info(f"{calc_date} 非交易日，跳过")
        return

    fund_list = get_active_funds(calc_date)
    total = len(fund_list)
    logger.info(f"共 {total} 只存续基金")

    batch_count = (total + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, total, BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"处理第 {batch_num}/{batch_count} 批...")

        batch_result = _process_batch(fund_list.iloc[i:i + BATCH_SIZE], calc_date_dt)
    #     if not batch_result.empty:
    #         with DorisConnector(ENV) as doris:
    #             doris.insert('tb_fd_perform_abs', batch_result)
    #
    # logger.info(f"{calc_date} 基金业绩指标计算完成")
    # logger.info("=" * 60)


if __name__ == '__main__':
    run('2026-01-06')
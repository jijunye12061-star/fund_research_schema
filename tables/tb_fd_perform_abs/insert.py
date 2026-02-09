"""
基金绝对收益指标表 - 数据计算【未完成】
计算基金在不同时间区间的绝对收益表现指标

关键设计：
- 年化收益率：期初期末净值，自然日天数（365天）
- 年化波动率：交易日收益率序列，交易日天数（252天）
- 收益率来源：NVGRWTD字段（小数形式，避免pct_change被周末污染）


@Author: 季俊晔
@Table: tb_fd_perform_abs
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.db_connector import OracleConnector, DorisConnector
from utils.common import (
    get_trade_calendar,
    find_nearest_trade_date,
    get_active_funds,
    safe_divide
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 配置部分 ====================

@dataclass
class PeriodConfig:
    """计算区间配置"""
    code: str
    name: str
    months: Optional[int] = None
    years: Optional[int] = None
    type: str = 'fixed'  # fixed/ytd/si


PERIOD_CONFIGS = [
    PeriodConfig('00', '近1月', months=1, type='fixed'),
    PeriodConfig('01', '近3月', months=3, type='fixed'),
    PeriodConfig('02', '近6月', months=6, type='fixed'),
    PeriodConfig('03', '近1年', years=1, type='fixed'),
    PeriodConfig('04', '近2年', years=2, type='fixed'),
    PeriodConfig('05', '近3年', years=3, type='fixed'),
    PeriodConfig('06', '近5年', years=5, type='fixed'),
    PeriodConfig('07', '今年来', type='ytd'),
    PeriodConfig('08', '成立来', type='si'),
]

RF_RATE = 0.02  # 无风险收益率
NATURAL_DAYS_PER_YEAR = 365
BATCH_SIZE = 100
MIN_DAYS_FOR_ANNUALIZATION = 21  # 成立满21个交易日才计算年化


@dataclass
class PeriodCalcInfo:
    """区间计算信息"""
    config: PeriodConfig
    start_date: datetime
    start_trade_date: datetime
    is_valid: bool


# ==================== 数据获取 ====================

def calculate_start_date(calc_date: datetime, period: PeriodConfig) -> datetime:
    """根据区间配置计算起始日期"""
    if period.type == 'fixed':
        if period.months is not None:
            return calc_date - relativedelta(months=period.months)
        elif period.years is not None:
            return calc_date - relativedelta(years=period.years)
    elif period.type == 'ytd':
        return datetime(calc_date.year, 1, 1)

    raise ValueError(f"无法计算起始日期: {period}")


def _get_nav_data_batch(fund_codes: List[str], calc_date: datetime) -> pd.DataFrame:
    """
    批量获取基金净值数据

    关键：使用NVGRWTD字段获取日收益率，避免pct_change被周末前值污染
    """
    fund_codes_str = "','".join(fund_codes)

    sql = f"""
    SELECT
        SECURITYCODE as c_fd_code,
        ENDDATE as c_trade_date,
        AANVPER as c_adj_nav,
        NVGRWTD as c_ret_1d
    FROM TYTFUND.FUND_DR_FUNDNV
    WHERE SECURITYCODE IN ('{fund_codes_str}')
      AND ENDDATE <= TO_DATE('{calc_date.strftime('%Y-%m-%d')}', 'YYYY-MM-DD')
      AND AANVPER IS NOT NULL
    """

    with OracleConnector() as oracle:
        df = oracle.query(sql)

    df.columns = df.columns.str.lower()
    df['c_trade_date'] = pd.to_datetime(df['c_trade_date'])
    df['c_adj_nav'] = pd.to_numeric(df['c_adj_nav'], errors='coerce')
    df['c_ret_1d'] = pd.to_numeric(df['c_ret_1d'], errors='coerce')

    return df


# ==================== 区间有效性判断 ====================

def _determine_valid_periods(
        estab_date: datetime,
        calc_date: datetime,
        trade_dates: Set[datetime]
) -> List[PeriodCalcInfo]:
    """判断哪些区间对该基金有效"""
    valid_periods = []

    for period in PERIOD_CONFIGS:
        if period.type == 'fixed':
            start_date = calculate_start_date(calc_date, period)
            is_valid = estab_date <= start_date
        elif period.type == 'ytd':
            start_date = datetime(calc_date.year, 1, 1)
            is_valid = estab_date <= start_date
        elif period.type == 'si':
            start_date = estab_date
            is_valid = True
        else:
            continue

        if is_valid:
            start_date = max(start_date, estab_date)
            start_trade_date = find_nearest_trade_date(start_date, trade_dates, 'after')

            valid_periods.append(PeriodCalcInfo(
                config=period,
                start_date=start_date,
                start_trade_date=start_trade_date,
                is_valid=True
            ))

    return valid_periods


# ==================== 指标计算 ====================

def _calc_period_return(nav_series: pd.Series) -> Optional[float]:
    """计算区间收益率(%)"""
    if len(nav_series) < 2 or nav_series.iloc[0] == 0:
        return None
    return ((nav_series.iloc[-1] / nav_series.iloc[0]) - 1) * 100


def _calc_annualized_return(nav_series: pd.Series, actual_natural_days: int) -> Optional[float]:
    """计算年化收益率(%) - 使用自然日天数"""
    if len(nav_series) < 2 or actual_natural_days == 0:
        return None

    if actual_natural_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    total_return = (nav_series.iloc[-1] / nav_series.iloc[0]) - 1
    years = actual_natural_days / NATURAL_DAYS_PER_YEAR

    if total_return <= -1:
        return None

    ann_return = (1 + total_return) ** (1 / years) - 1
    return ann_return * 100


def _calc_annualized_volatility(returns: pd.Series, actual_trade_days: int) -> Optional[float]:
    """计算年化波动率(%) - 使用交易日天数"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    if actual_trade_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    daily_vol = returns.std()
    annualization_factor = np.sqrt(252 / actual_trade_days * len(returns))

    return daily_vol * annualization_factor * 100


def _calc_upside_volatility(returns: pd.Series, actual_trade_days: int) -> Optional[float]:
    """计算上行波动率(%)"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    if actual_trade_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    upside_returns = returns[returns > 0]
    if len(upside_returns) < 2:
        return None

    daily_vol = upside_returns.std()
    annualization_factor = np.sqrt(252 / actual_trade_days * len(returns))

    return daily_vol * annualization_factor * 100


def _calc_downside_volatility(returns: pd.Series, actual_trade_days: int) -> Optional[float]:
    """计算下行波动率(%)"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    if actual_trade_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    downside_returns = returns[returns < 0]
    if len(downside_returns) < 2:
        return None

    daily_vol = downside_returns.std()
    annualization_factor = np.sqrt(252 / actual_trade_days * len(returns))

    return daily_vol * annualization_factor * 100


def _calc_max_drawdown(nav_series: pd.Series) -> Optional[float]:
    """计算最大回撤(%) - 正数表示"""
    if len(nav_series) < 2:
        return None

    cummax = nav_series.cummax()
    drawdown = (nav_series - cummax) / cummax
    max_dd = abs(drawdown.min())

    return max_dd * 100


def _calc_sharpe_ratio(returns: pd.Series, actual_trade_days: int, rf_rate: float = RF_RATE) -> Optional[float]:
    """计算夏普比率"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    if actual_trade_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    daily_rf = rf_rate / 252
    excess_returns = returns - daily_rf

    mean_excess = excess_returns.mean()
    std_val = excess_returns.std()

    annualization_factor = np.sqrt(252 / actual_trade_days * len(returns))

    return safe_divide(
        mean_excess * annualization_factor,
        std_val,
        default=None,
        min_denominator=1e-8,
        max_result=100
    )


def _calc_calmar_ratio(returns: pd.Series, max_drawdown: float, actual_trade_days: int) -> Optional[float]:
    """计算卡玛比率"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    annual_return = (1 + returns.mean()) ** (252 / actual_trade_days * len(returns)) - 1

    return safe_divide(
        annual_return,
        abs(max_drawdown / 100),
        default=None,
        min_denominator=1e-6,
        max_result=100
    )


def _calc_sortino_ratio(returns: pd.Series, actual_trade_days: int, rf_rate: float = RF_RATE) -> Optional[float]:
    """计算索提诺比率"""
    if len(returns) < 2 or actual_trade_days == 0:
        return None

    if actual_trade_days < MIN_DAYS_FOR_ANNUALIZATION:
        return None

    daily_rf = rf_rate / 252
    excess_returns = returns - daily_rf

    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 0

    annualization_factor = np.sqrt(252 / actual_trade_days * len(returns))

    return safe_divide(
        excess_returns.mean() * annualization_factor,
        downside_std,
        default=None,
        min_denominator=1e-8,
        max_result=100
    )


def _calc_skewness(returns: pd.Series) -> Optional[float]:
    """计算偏度"""
    if len(returns) < 3:
        return None
    return returns.skew()


def _calc_kurtosis(returns: pd.Series) -> Optional[float]:
    """计算峰度"""
    if len(returns) < 4:
        return None
    return returns.kurtosis()


def _calc_new_high_ratio(nav_series: pd.Series) -> Optional[float]:
    """计算净值创新高天数比例(%)"""
    if len(nav_series) < 2:
        return None
    is_new_high = nav_series >= nav_series.cummax()
    return (is_new_high.sum() / len(nav_series)) * 100


# ==================== 数据准备和计算 ====================

def _prepare_period_data(
        nav_df: pd.DataFrame,
        start_date: datetime,
        calc_date: datetime,
        trade_dates: Set[datetime]
) -> tuple[pd.Series, pd.Series, int, int]:
    """
    准备区间数据

    Returns:
        nav_series: 净值序列（含非交易日）
        returns: 交易日收益率序列
        actual_natural_days: 自然日天数
        actual_trade_days: 交易日天数
    """
    # 筛选区间数据
    period_nav = nav_df[
        (nav_df['c_trade_date'] >= start_date) &
        (nav_df['c_trade_date'] <= calc_date)
        ].copy().sort_values('c_trade_date')

    if len(period_nav) < 2:
        return None, None, 0, 0

    # 过滤到交易日（避免周末前值污染）
    period_nav_trade = period_nav[period_nav['c_trade_date'].isin(trade_dates)].copy()

    if len(period_nav_trade) < 2:
        return None, None, 0, 0

    # 提取序列
    nav_series = period_nav['c_adj_nav']  # 含非交易日，用于计算收益率
    returns = period_nav_trade['c_ret_1d'].dropna()  # 仅交易日，用于波动率

    # 计算天数
    actual_natural_days = (period_nav['c_trade_date'].iloc[-1] -
                           period_nav['c_trade_date'].iloc[0]).days
    actual_trade_days = len(period_nav_trade)

    return nav_series, returns, actual_natural_days, actual_trade_days


def _calc_all_metrics(
        nav_series: pd.Series,
        returns: pd.Series,
        actual_natural_days: int,
        actual_trade_days: int
) -> Dict:
    """批量计算所有指标"""
    mdd = _calc_max_drawdown(nav_series)

    return {
        'c_period_ret': _calc_period_return(nav_series),
        'c_ann_ret': _calc_annualized_return(nav_series, actual_natural_days),
        'c_ann_vol': _calc_annualized_volatility(returns, actual_trade_days),
        'c_up_side_vol': _calc_upside_volatility(returns, actual_trade_days),
        'c_down_side_vol': _calc_downside_volatility(returns, actual_trade_days),
        'c_mdd': mdd,
        'c_sharpe': _calc_sharpe_ratio(returns, actual_trade_days),
        'c_calmar': _calc_calmar_ratio(returns, mdd, actual_trade_days),
        'c_sortino': _calc_sortino_ratio(returns, actual_trade_days),
        'c_skewness': _calc_skewness(returns),
        'c_kurtosis': _calc_kurtosis(returns),
        'c_break_ratio': _calc_new_high_ratio(nav_series)
    }


def _calculate_fund_metrics(
        fund_code: str,
        calc_date: datetime,
        nav_df: pd.DataFrame,
        estab_date: datetime,
        trade_dates: Set[datetime]
) -> List[Dict]:
    """计算单只基金的所有有效区间指标"""
    results = []

    nav_df = nav_df.sort_values('c_trade_date')
    calc_date = pd.to_datetime(calc_date)

    if calc_date not in nav_df['c_trade_date'].values:
        logger.warning(f"基金 {fund_code} 在 {calc_date.date()} 无净值数据")
        return results

    valid_periods = _determine_valid_periods(estab_date, calc_date, trade_dates)

    for period_info in valid_periods:
        nav_series, returns, actual_natural_days, actual_trade_days = _prepare_period_data(
            nav_df,
            period_info.start_date,
            calc_date,
            trade_dates
        )

        if nav_series is None or len(returns) < 1:
            continue

        metrics = _calc_all_metrics(nav_series, returns, actual_natural_days, actual_trade_days)

        result = {
            'c_fd_code': fund_code,
            'c_trade_date': calc_date.date(),
            'c_period_code': period_info.config.code,
            **metrics
        }

        results.append(result)

    return results


# ==================== 批量处理 ====================

def _process_batch(
        fund_batch: pd.DataFrame,
        calc_date: datetime,
        trade_dates: Set[datetime]
) -> pd.DataFrame:
    """处理一批基金"""
    fund_codes = fund_batch['c_fd_code'].tolist()

    nav_df = _get_nav_data_batch(fund_codes, calc_date)

    if len(nav_df) == 0:
        logger.warning(f"本批 {len(fund_codes)} 只基金无净值数据")
        return pd.DataFrame()

    all_results = []
    for _, fund_info in fund_batch.iterrows():
        fund_code = fund_info['c_fd_code']
        estab_date = pd.to_datetime(fund_info['c_estabdate'])

        fund_nav = nav_df[nav_df['c_fd_code'] == fund_code].copy()

        if len(fund_nav) == 0:
            continue

        fund_results = _calculate_fund_metrics(
            fund_code,
            calc_date,
            fund_nav,
            estab_date,
            trade_dates
        )

        all_results.extend(fund_results)

    if len(all_results) > 0:
        result_df = pd.DataFrame(all_results)
        logger.info(f"本批生成 {len(result_df)} 条指标数据")
        return result_df
    else:
        return pd.DataFrame()


# ==================== 主函数 ====================

def run(calc_date: str = None):
    """
    主入口函数 - 计算指定日期所有基金的业绩指标

    Args:
        calc_date: 计算日期 'YYYY-MM-DD'，默认为None时不执行
    """
    if calc_date is None:
        logger.info("未指定计算日期，跳过执行")
        return

    logger.info("=" * 60)
    logger.info(f"开始计算 {calc_date} 的基金业绩指标")

    calc_date_dt = datetime.strptime(calc_date, '%Y-%m-%d')

    # 1. 获取交易日历
    earliest_possible_date = '1991-11-01'
    trade_dates = get_trade_calendar(earliest_possible_date, calc_date)
    logger.info(f"获取交易日历: {len(trade_dates)} 个交易日")

    # 2. 获取存续基金列表
    fund_list = get_active_funds(calc_date)
    total_funds = len(fund_list)

    if total_funds == 0:
        logger.error("未找到存续基金")
        return

    logger.info(f"共 {total_funds} 只存续基金")

    # 3. 分批处理
    batch_count = (total_funds + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, total_funds, BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"处理第 {batch_num}/{batch_count} 批基金...")

        fund_batch = fund_list.iloc[i:i + BATCH_SIZE]
        batch_results = _process_batch(fund_batch, calc_date_dt, trade_dates)

        if len(batch_results) > 0:
            with DorisConnector() as doris:
                doris.insert("tb_fd_perform_abs", batch_results)

    logger.info(f"{calc_date} 基金业绩指标计算完成")
    logger.info("=" * 60)


# ==================== 测试入口 ====================

if __name__ == '__main__':
    # 测试：检查是否为交易日
    test_date = '2024-11-27'

    trading_dts = get_trade_calendar(test_date, test_date)
    if pd.to_datetime(test_date) in trading_dts:
        run(test_date)
    else:
        logger.info(f"{test_date} 非交易日，跳过计算")
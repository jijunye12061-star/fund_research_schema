"""
公共函数模块 - 跨表复用的数据获取和工具函数

@Author: 季俊晔
@Project: fund_research_db
"""
import pandas as pd
from typing import Optional
from datetime import datetime
from enum import Enum

from utils.db_connector import DorisConnector

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================

# ==================== 日期相关代码 ====================

def get_trade_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """获取交易日历，返回交易日集合"""
    sql = f"""
    SELECT c_date
    FROM tytdata.tb_trade_calendar
    WHERE c_date >= :start_date
      AND c_date <= :end_date
      AND c_is_trade = 1
    order by c_date
    """

    with DorisConnector(ENV) as doris:
        df = doris.query(sql, start_date=start_date, end_date=end_date)

    return pd.DatetimeIndex(df['c_date'])


def find_nearest_trade_date(
    target_date: str,
    trade_dates: pd.DatetimeIndex,
    direction: str = 'before'
) -> datetime:
    """
    查找最近的交易日

    Args:
        target_date: 目标日期
        trade_dates: 交易日集合
        direction: 'before' 向前找, 'after' 向后找
    """
    target_date = pd.to_datetime(target_date)
    if target_date in trade_dates:
        return target_date

    sorted_dates = sorted(trade_dates)

    if direction == 'before':
        valid_dates = [d for d in sorted_dates if d <= target_date]
        return valid_dates[-1] if valid_dates else sorted_dates[0]
    else:
        valid_dates = [d for d in sorted_dates if d >= target_date]
        return valid_dates[0] if valid_dates else sorted_dates[-1]


def generate_report_dates(last_report_dt: str, n: int) -> list[str]:
    """生成最近n个报告期日期

    Args:
        last_report_dt: 最后报告期 'YYYY-MM-DD'
        n: 报告期数量

    Returns:
        升序排列的报告期列表
    """
    quarter_ends = ['03-31', '06-30', '09-30', '12-31']
    assert last_report_dt[5:] in quarter_ends, f"日期必须为季度末: {quarter_ends}"
    dates = pd.date_range(end=last_report_dt, periods=n, freq='3ME')
    return [d.strftime('%Y-%m-%d') for d in sorted(dates)]


def get_last_quarter_end(calc_date: str) -> str:
    """获取上一报告期（季度末）日期

    Args:
        calc_date: 执行日期 'YYYY-MM-DD'

    Returns:
        上一季度末日期 'YYYY-MM-DD'

    Examples:
        '2025-01-31' → '2024-12-31'
        '2025-04-30' → '2025-03-31'
    """
    date = pd.to_datetime(calc_date)
    return (date - pd.offsets.QuarterEnd(1)).strftime('%Y-%m-%d')

# ==================== 基金基本信息获取 ====================

def get_active_funds(calc_date: str) -> pd.DataFrame:
    """获取截至指定日期仍存续的基金列表"""
    sql = f"""
    SELECT 
        c_fd_code,
        c_estabdate,
        c_terminate_date
    FROM tytdata.tb_fd_basic_info
    WHERE c_estabdate <= :calc_date
      AND (c_terminate_date IS NULL OR c_terminate_date > :calc_date)
    ORDER BY c_fd_code
    """

    with DorisConnector('dev') as doris:
        df = doris.query(sql, calc_date=calc_date)

    return df

# ==================== 报告期披露截止日调度 ====================


class ReportFreq(Enum):
    """基金报告披露频率

    QUARTERLY   - 季报(15工作日): Q1≈0422 / Q2≈0722 / Q3≈1022 / Q4≈次年0122
    SEMI_ANNUAL - 半年报/年报:   Q2→0829(60日) / Q4→次年0331(90日)
    """
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"


def get_quarterly_deadline(report_date: str) -> pd.Timestamp:
    """季报披露截止日：报告期结束后第15个工作日"""
    rd = pd.Timestamp(report_date)
    start = (rd + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    end = (rd + pd.Timedelta(days=30)).strftime('%Y-%m-%d')
    trade_dates = get_trade_calendar(start, end)
    return trade_dates[14]  # 0-indexed，第15个工作日


def get_semiannual_deadline(report_date: str) -> pd.Timestamp:
    """半年报/年报披露截止日：H1→60自然日，Annual→90自然日"""
    rd = pd.Timestamp(report_date)
    days = 60 if rd.month == 6 else 90
    return rd + pd.Timedelta(days=days)


def should_run(calc_date: str, freq: ReportFreq, window: int = 2) -> tuple[bool, str]:
    """判断当前执行日期是否命中某个报告期的披露截止窗口

    Args:
        calc_date: DS传入的执行日期，格式 'YYYY-MM-DD'
        freq:      数据源披露频率
        window:    截止日后容错天数（截止日当天 + window天内均可触发）

    Returns:
        (should_run, report_date): 是否执行 + 对应报告期字符串

    Examples:
        should_run('2026-04-22', ReportFreq.QUARTERLY)   → (True,  '2026-03-31')
        should_run('2026-04-20', ReportFreq.QUARTERLY)   → (False, '')
        should_run('2026-08-29', ReportFreq.SEMI_ANNUAL) → (True,  '2026-06-30')
    """
    cd = pd.Timestamp(calc_date)
    last_qe = get_last_quarter_end(calc_date)
    recent_quarters = generate_report_dates(last_qe, 3)  # 最近3个季度末

    for qe_str in reversed(recent_quarters):  # 从最近往前匹配
        qe = pd.Timestamp(qe_str)

        if freq == ReportFreq.QUARTERLY:
            deadline = get_quarterly_deadline(qe_str)
        else:  # SEMI_ANNUAL 只看 06-30 和 12-31
            if qe.month not in (6, 12):
                continue
            deadline = get_semiannual_deadline(qe_str)

        if deadline <= cd <= deadline + pd.Timedelta(days=window):
            return True, qe_str

    return False, ''


# ==================== 其他通用函数 ====================

def safe_divide(
    numerator: float,
    denominator: float,
    default: Optional[float] = None,
    min_denominator: float = 1e-10,
    max_result: Optional[float] = None
) -> Optional[float]:
    """
    安全除法，避免除零和异常值

    Args:
        numerator: 分子
        denominator: 分母
        default: 除零时返回值
        min_denominator: 分母最小阈值
        max_result: 结果最大值限制
    """
    if abs(denominator) < min_denominator:
        return default

    result = numerator / denominator

    if max_result is not None and abs(result) > max_result:
        return default

    return result


if __name__ == '__main__':
    test_calender = get_trade_calendar('2026-02-01', '2026-02-13')
    test_result = get_active_funds('2025-01-31')

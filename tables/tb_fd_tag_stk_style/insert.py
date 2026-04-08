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
import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ENV = 'dev'

FACTOR_CODES = ['VALUE', 'GROWTH', 'MOMENTUM', 'PROF', 'QUALITY', 'DTOP']

OUTPUT_COLS = [
    'c_report_date', 'c_fd_code',
    'c_size_score', 'c_size_tag',
    'c_value_score', 'c_growth_score', 'c_vg_tag',
    'c_momentum_score', 'c_momentum_tag',
    'c_profit_score', 'c_profit_tag',
    'c_quality_score', 'c_quality_tag',
    'c_dividend_score', 'c_dividend_tag',
]


# ==================== 日期工具 ====================

def _get_semi_annual_periods(calc_date: str) -> list[str]:
    """近4期半年报日期（均 <= calc_date）"""
    return [d for d in generate_report_dates(calc_date, 8)
            if d[5:] in ('06-30', '12-31')]


def _get_trade_date(doris: DorisConnector, report_date: str) -> str:
    """取报告期对应的最近交易日（tb_trade_calendar.c_max_trade_date）"""
    df = doris.query(
        "SELECT c_max_trade_date FROM tytdata.tb_trade_calendar WHERE c_date = :d",
        d=report_date
    )
    return str(df['c_max_trade_date'].iloc[0])


# ==================== 数据查询 ====================

def _get_fund_codes(doris: DorisConnector, report_date: str) -> list[str]:
    """取前四类基金代码"""
    sql = """
    SELECT DISTINCT c_fd_code FROM tytdata.tb_fd_category
    WHERE c_type1_code IN ('001','002','003','004')
      AND c_report_date = :report_date
    """
    return doris.query(sql, report_date=report_date)['c_fd_code'].tolist()


def _get_hk_funds(doris: DorisConnector, report_date: str) -> set:
    """港股标签基金集合（动量/盈利/质量跨基金分位时排除）"""
    sql = """
    SELECT c_fd_code FROM tytdata.tb_fd_tag_stk_region_sector
    WHERE c_report_date = :d AND c_region_tag = '港股'
    """
    return set(doris.query(sql, d=report_date)['c_fd_code'].tolist())


def _query_barra(doris: DorisConnector, trade_date: str) -> pd.DataFrame:
    """全市场A股流通市值（亿元）"""
    sql = """
    SELECT c_stk_code, c_float_mv / 1e8 AS float_mv
    FROM tytdata.tb_stk_barra_status
    WHERE c_trade_date = :d
    """
    return doris.query(sql, d=trade_date)


def _query_factors(doris: DorisConnector, trade_date: str) -> pd.DataFrame:
    """全市场A股因子值（宽表：stk_code × factor）"""
    sql = """
    SELECT c_stk_code, c_factor_code, c_factor_value
    FROM tytdata.tb_stk_risk_factor
    WHERE c_trade_date = :d
      AND c_factor_code IN ('VALUE','GROWTH','MOMENTUM','PROF','QUALITY','DTOP')
    """
    df = doris.query(sql, d=trade_date)
    pivot = df.pivot(index='c_stk_code', columns='c_factor_code',
                     values='c_factor_value')
    pivot.columns.name = None
    return pivot.reset_index()


def _query_portfolio(doris: DorisConnector, fund_codes: list[str],
                     report_date: str) -> pd.DataFrame:
    """基金A股持仓（去重：同一fd+stk取MIN c_style）"""
    sql = """
    SELECT c_fd_code, c_stk_code, c_style, c_hold_value
    FROM tytdata.tb_fd_portfolio_stk
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style IN ('02','04')
      AND c_hold_value > 0
      AND LENGTH(c_stk_code) = 6
    """
    df = doris.query_batch(sql, code_list=fund_codes, report_date=report_date)
    df = (df.sort_values('c_style')
            .drop_duplicates(subset=['c_fd_code', 'c_stk_code'], keep='first'))
    return df[['c_fd_code', 'c_stk_code', 'c_hold_value']]


# ==================== 单期计算 ====================

def _calc_size_threshold(barra: pd.DataFrame) -> tuple[float, float]:
    """全市场SIZE阈值：流通市值累计50%/70%时的边界市值（亿元）"""
    s = barra.sort_values('float_mv', ascending=False)
    total = s['float_mv'].sum()
    cumsum = s['float_mv'].cumsum()
    size_50 = float(s.loc[cumsum >= total * 0.50, 'float_mv'].iloc[0])
    size_70 = float(s.loc[cumsum >= total * 0.70, 'float_mv'].iloc[0])
    return size_50, size_70


def _calc_vg_threshold(factors: pd.DataFrame) -> tuple[float, float]:
    """全市场VALUE-GROWTH spread 67%/33%分位"""
    spread = (factors['VALUE'] - factors['GROWTH']).dropna()
    return float(spread.quantile(0.67)), float(spread.quantile(0.33))


def _calc_fund_scores(portfolio: pd.DataFrame, barra: pd.DataFrame,
                      factors: pd.DataFrame) -> pd.DataFrame:
    """单期：计算各基金持仓加权因子得分"""
    # inner join barra = 只保留A股持仓（港股标的在barra中无记录）
    df = portfolio.merge(barra, on='c_stk_code', how='inner')
    df = df.merge(factors, on='c_stk_code', how='left')

    w = df['c_hold_value']
    df['wt_size'] = w * df['float_mv']
    for fc in FACTOR_CODES:
        df[f'wt_{fc}'] = w * df[fc]
        df[f'w_{fc}'] = w.where(df[fc].notna(), 0.0)

    agg = {'c_hold_value': 'sum', 'wt_size': 'sum'}
    for fc in FACTOR_CODES:
        agg[f'wt_{fc}'] = 'sum'
        agg[f'w_{fc}'] = 'sum'

    g = df.groupby('c_fd_code').agg(agg).reset_index()
    g['size_score'] = g['wt_size'] / g['c_hold_value']
    for fc in FACTOR_CODES:
        g[fc.lower() + '_score'] = g[f'wt_{fc}'] / g[f'w_{fc}'].replace(0.0, np.nan)

    score_cols = ['size_score'] + [fc.lower() + '_score' for fc in FACTOR_CODES]
    return g[['c_fd_code'] + score_cols]


# ==================== 标签打分 ====================

def _assign_size_vg_tags(result: pd.DataFrame, avg_50: float, avg_70: float,
                          avg_vg1: float, avg_vg2: float) -> None:
    """原地打市值标签和价值-成长标签"""
    # SIZE tag（先算字符串，再单独置空，避免 numpy 新版 float/str 混用报错）
    result['c_size_tag'] = np.where(result['c_size_score'] > avg_50, '大盘',
                           np.where(result['c_size_score'] > avg_70, '中盘', '小盘'))
    result.loc[result['c_size_score'].isna(), 'c_size_tag'] = None

    # VG tag
    spread = result['c_value_score'] - result['c_growth_score']
    is_value = (result['c_value_score'] > 0) & (spread >= avg_vg1)
    is_growth = (result['c_growth_score'] > 0) & (spread <= avg_vg2)
    is_garp = (result['c_value_score'] > 0) & (result['c_growth_score'] > 0) & ~is_value & ~is_growth
    result['c_vg_tag'] = np.select([is_value, is_growth, is_garp],
                                   ['价值', '成长', 'GARP'], default='均衡')
    both_nan = result['c_value_score'].isna() & result['c_growth_score'].isna()
    result.loc[both_nan, 'c_vg_tag'] = None


def _assign_relative_tags(result: pd.DataFrame, hk_funds: set) -> None:
    """原地打动量/盈利/质量标签（跨基金70%/30%分位，排除港股基金）"""
    non_hk = ~result['c_fd_code'].isin(hk_funds)
    tag_config = [
        ('c_momentum_score', 'c_momentum_tag', '高动量', '中动量', '低动量'),
        ('c_profit_score',   'c_profit_tag',   '高盈利', '中盈利', '低盈利'),
        ('c_quality_score',  'c_quality_tag',  '高质量', '中质量', '低质量'),
        ('c_dividend_score', 'c_dividend_tag', '高股息', '中股息', '低股息'),
    ]
    for score_col, tag_col, high, mid, low in tag_config:
        valid = result.loc[non_hk, score_col].dropna()
        p70, p30 = valid.quantile(0.70), valid.quantile(0.30)
        result[tag_col] = np.select(
            [result[score_col] >= p70, result[score_col] <= p30],
            [high, low], default=mid
        )
        # 港股基金及无得分基金不打标签
        result.loc[~non_hk | result[score_col].isna(), tag_col] = np.nan


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date 为报告期如 '2025-06-30'"""
    s_periods = _get_semi_annual_periods(calc_date)
    logger.info(f"计算 {calc_date}，半年报窗口: {s_periods}")

    with DorisConnector(ENV) as doris:
        fund_codes = _get_fund_codes(doris, calc_date)
        hk_funds = _get_hk_funds(doris, calc_date)
        logger.info(f"基金 {len(fund_codes)} 只，港股基金 {len(hk_funds)} 只")

        period_scores, size_thresholds, vg_thresholds = [], [], []
        for rd in s_periods:
            td = _get_trade_date(doris, rd)
            logger.info(f"期 {rd} → 交易日 {td}")
            barra = _query_barra(doris, td)
            factors = _query_factors(doris, td)
            portfolio = _query_portfolio(doris, fund_codes, rd)
            scores = _calc_fund_scores(portfolio, barra, factors)
            period_scores.append(scores)
            size_thresholds.append(_calc_size_threshold(barra))
            vg_thresholds.append(_calc_vg_threshold(factors))

        # 4期均值
        score_cols = ['size_score'] + [fc.lower() + '_score' for fc in FACTOR_CODES]
        all_df = pd.concat(period_scores, ignore_index=True)
        result = all_df.groupby('c_fd_code')[score_cols].mean().reset_index()
        result.rename(columns={
            'size_score': 'c_size_score',
            'value_score': 'c_value_score', 'growth_score': 'c_growth_score',
            'momentum_score': 'c_momentum_score', 'prof_score': 'c_profit_score',
            'quality_score': 'c_quality_score', 'dtop_score': 'c_dividend_score',
        }, inplace=True)

        # 均值阈值
        avg_50  = float(np.mean([t[0] for t in size_thresholds]))
        avg_70  = float(np.mean([t[1] for t in size_thresholds]))
        avg_vg1 = float(np.mean([t[0] for t in vg_thresholds]))
        avg_vg2 = float(np.mean([t[1] for t in vg_thresholds]))

        _assign_size_vg_tags(result, avg_50, avg_70, avg_vg1, avg_vg2)
        _assign_relative_tags(result, hk_funds)

        result['c_report_date'] = pd.to_datetime(calc_date)
        doris.insert('tb_fd_tag_stk_style', result[OUTPUT_COLS])

    logger.info(f"写入完成: {len(result)} 条")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        # DS 调度入口：传入 '20250630' 格式
        raw = sys.argv[1]
        run(f'{raw[:4]}-{raw[4:6]}-{raw[6:]}')
    else:
        # ── 单期运行 ──────────────────────────────────────────
        # run('2025-12-31')

        # ── 历史补数：2016-03-31 起，季度频率 ─────────────────
        hist_dates = generate_report_dates('2025-12-31', 40)
        for dt in hist_dates:
            run(dt)

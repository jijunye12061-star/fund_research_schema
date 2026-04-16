"""
模块四：业绩表现

输出 data/m4_perf.xlsx
  Sheet1: 业绩明细（含同类分位数）
  Sheet2: 分品类业绩统计（分位数 + 正收益占比 + 极差）
  Sheet3: 各品类收益 TOP5（规模 > 1亿）
  Sheet4: 大规模产品业绩（规模 TOP20）
  Sheet5: 基金公司平均收益（规模 TOP20 公司）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.db_connector import DorisConnector
from utils.log import setup_logger
from config import (
    REPORT_DATE, PERF_DATE,
    fetch_fi_universe, save_excel, date_to_style,
)

logger = setup_logger(__name__)
ENV = 'dev'


# ── 数据获取 ──────────────────────────────────────────────────────


def _fetch_perf(doris: DorisConnector, fd_codes: list[str]) -> pd.DataFrame:
    """查询当季收益(01)和YTD收益(07)"""
    sql = """
    SELECT c_fd_code, c_period_code,
           c_period_ret, c_mdd, c_sharpe, c_sortino
    FROM tb_fd_perform_abs
    WHERE c_trade_date  = :perf_date
      AND c_period_code IN ('01', '07')
      AND c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes,
                             perf_date=PERF_DATE)


def _fetch_nav(doris: DorisConnector) -> pd.DataFrame:
    """查询当期规模（亿），用于规模筛选和 TOP20"""
    sql = """
    SELECT c_fd_code, c_fund_nav_total
    FROM tb_fd_asset_allocation
    WHERE c_report_date = :report_date
      AND c_style       = :style
      AND c_is_stat     = -1
    """
    return doris.query(sql, report_date=REPORT_DATE, style=date_to_style(REPORT_DATE))


# ── 组装 ──────────────────────────────────────────────────────────


def _pivot_perf(perf_df: pd.DataFrame) -> pd.DataFrame:
    """将 period_code 行转为列"""
    p01 = perf_df[perf_df['c_period_code'] == '01'][
        ['c_fd_code', 'c_period_ret', 'c_mdd', 'c_sharpe', 'c_sortino']
    ].rename(columns={
        'c_period_ret': '当季收益%',
        'c_mdd': '当季最大回撤%',
        'c_sharpe': '夏普比率',
        'c_sortino': '索提诺比率',
    })
    p07 = perf_df[perf_df['c_period_code'] == '07'][
        ['c_fd_code', 'c_period_ret']
    ].rename(columns={'c_period_ret': 'YTD收益%'})
    return p01.merge(p07, on='c_fd_code', how='left')


def _build_detail(universe: pd.DataFrame,
                  perf_wide: pd.DataFrame,
                  nav_df: pd.DataFrame) -> pd.DataFrame:
    nav_df = nav_df.copy()
    nav_df['规模(亿)'] = (nav_df['c_fund_nav_total'] / 1e8).round(4)

    df = universe.merge(perf_wide, on='c_fd_code', how='left')
    df = df.merge(nav_df[['c_fd_code', '规模(亿)']], on='c_fd_code', how='left')

    # 同类分位数（当季收益%，分 c_type2_name 组内排名）
    df['同类收益分位'] = df.groupby('c_type2_name')['当季收益%'].rank(pct=True).round(4)

    return df[[
        'c_fd_code', 'c_short_name', 'c_type2_name', 'c_company_name',
        '规模(亿)', '当季收益%', 'YTD收益%', '当季最大回撤%', '夏普比率', '索提诺比率',
        '同类收益分位',
    ]].rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型', 'c_company_name': '基金公司',
    })


def _build_category_stats(detail: pd.DataFrame) -> pd.DataFrame:
    """各品类收益分位数 + 正收益占比 + 极差"""
    rows = []
    for cat, grp in detail.groupby('二级类型'):
        ret = grp['当季收益%'].dropna()
        if ret.empty:
            continue
        rows.append({
            '二级类型': cat,
            '基金数量': len(grp),
            'P10%': ret.quantile(0.10).round(2),
            'P25%': ret.quantile(0.25).round(2),
            '中位数%': ret.quantile(0.50).round(2),
            'P75%': ret.quantile(0.75).round(2),
            'P90%': ret.quantile(0.90).round(2),
            '正收益占比%': round((ret > 0).mean() * 100, 1),
            '极差%': round(ret.max() - ret.min(), 2),
        })
    return pd.DataFrame(rows).sort_values('中位数%', ascending=False).reset_index(drop=True)


def _build_top5_by_category(detail: pd.DataFrame) -> pd.DataFrame:
    """各品类收益 TOP5（规模 > 1亿）"""
    filtered = detail[detail['规模(亿)'] > 1].copy()
    frames = []
    for cat, grp in filtered.groupby('二级类型'):
        top5 = grp.nlargest(5, '当季收益%').copy()
        top5.insert(0, '品类', cat)
        top5.insert(1, '品类内排名', range(1, len(top5) + 1))
        frames.append(top5)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _build_large_fund_perf(detail: pd.DataFrame) -> pd.DataFrame:
    """规模 TOP20 产品的业绩"""
    top20 = detail.nlargest(20, '规模(亿)').copy()
    top20.insert(0, '规模排名', range(1, len(top20) + 1))
    return top20.reset_index(drop=True)


def _build_company_avg(detail: pd.DataFrame) -> pd.DataFrame:
    """规模 TOP20 公司的平均当季收益（按公司管理规模加权平均）"""
    company_scale = detail.groupby('基金公司')['规模(亿)'].sum().nlargest(20)
    top20_companies = set(company_scale.index)
    sub = detail[detail['基金公司'].isin(top20_companies)].copy()

    def wavg(g):
        w = g['规模(亿)'].fillna(0)
        r = g['当季收益%'].fillna(np.nan)
        mask = r.notna() & (w > 0)
        if mask.sum() == 0:
            return np.nan
        return (r[mask] * w[mask]).sum() / w[mask].sum()

    grp = sub.groupby('基金公司').apply(wavg, include_groups=False).rename('加权平均当季收益%').reset_index()
    grp = grp.merge(company_scale.rename('管理规模(亿)').reset_index(), on='基金公司')
    grp['加权平均当季收益%'] = grp['加权平均当季收益%'].round(2)
    grp['管理规模(亿)'] = grp['管理规模(亿)'].round(2)
    grp = grp.sort_values('管理规模(亿)', ascending=False).reset_index(drop=True)
    grp.insert(0, '排名', range(1, len(grp) + 1))
    return grp


# ── 主流程 ────────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        logger.info("=== 模块四：业绩表现 ===")

        universe = fetch_fi_universe(doris, REPORT_DATE)
        fd_codes = universe['c_fd_code'].tolist()
        perf_df  = _fetch_perf(doris, fd_codes)
        nav_df   = _fetch_nav(doris)

    perf_wide = _pivot_perf(perf_df)
    detail    = _build_detail(universe, perf_wide, nav_df)
    logger.info(f"有业绩数据基金数：{detail['当季收益%'].notna().sum()}")

    save_excel({
        '业绩明细':       detail,
        '分品类业绩统计':  _build_category_stats(detail),
        '各品类收益TOP5':  _build_top5_by_category(detail),
        '大规模产品业绩':  _build_large_fund_perf(detail),
        '基金公司平均收益': _build_company_avg(detail),
    }, 'm4_perf.xlsx')
    logger.info("模块四完成")


if __name__ == '__main__':
    run()

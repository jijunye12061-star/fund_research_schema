"""
模块五：持仓配置

输出 data/m5_holding.xlsx
  Sheet1:  资产配置总览（每只基金：股票%/转债%/权益%/港股%，本期+上期）
  Sheet2:  分品类仓位中位数（近4期对比）
  Sheet3:  重仓股明细（基金×股票，含行业/占净值比）
  Sheet4:  重仓股行业汇总（本期+上期+变化，分品类）
  Sheet5:  前十大重仓股排名（按持仓市值加总，分品类）
  Sheet6:  转股期转债持仓明细（基金×转债，含评级/正股代码/正股行业）
  Sheet7:  转债评级分布（本期+上期）
  Sheet8:  转债行业分布及增减持
  Sheet9:  前20大重仓转债（按持仓市值加总）
  Sheet10: 债券风格标签汇总（tb_fd_tag_bd_style）
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.db_connector import DorisConnector
from utils.log import setup_logger
from config import (
    REPORT_DATE, PREV_DATE, RECENT_4_DATES,
    fetch_fi_universe, save_excel, date_to_style,
)

logger = setup_logger(__name__)
ENV = 'dev'


# ── 数据获取 ──────────────────────────────────────────────────────


def _fetch_asset_alloc(doris: DorisConnector, report_date: str) -> pd.DataFrame:
    sql = """
    SELECT c_fd_code,
           c_stk_total_ratio,
           c_bd_convertible_ratio,
           c_stk_equity_ratio,
           c_stk_hk_connect_ratio
    FROM tb_fd_asset_allocation
    WHERE c_report_date = :report_date
      AND c_style       = :style
      AND c_is_stat     = -1
    """
    return doris.query(sql, report_date=report_date, style=date_to_style(report_date))


def _fetch_asset_alloc_multi(doris: DorisConnector, dates: list[str]) -> pd.DataFrame:
    """批量查近4期资产配置（用于 Sheet2 分品类中位数对比）"""
    sql = """
    SELECT c_fd_code, c_report_date,
           c_stk_total_ratio, c_bd_convertible_ratio, c_stk_equity_ratio
    FROM tb_fd_asset_allocation
    WHERE c_report_date >= :start_date
      AND c_report_date <= :end_date
      AND c_style IN ('01', '03', '05', '06')
      AND c_is_stat = -1
    """
    df = doris.query(sql, start_date=dates[0], end_date=dates[-1])
    valid = set(dates)
    return df[df['c_report_date'].astype(str).isin(valid)]


def _fetch_stk_holdings(doris: DorisConnector, fd_codes: list[str],
                        report_date: str) -> pd.DataFrame:
    sql = """
    SELECT p.c_fd_code, p.c_stk_code, p.c_hold_value, p.c_nav_ratio,
           b.c_stk_name,
           d.c_param_name AS c_industry
    FROM tb_fd_portfolio_stk p
    LEFT JOIN tb_stk_basic_info b ON b.c_stk_code = p.c_stk_code
    LEFT JOIN tb_stk_industry si
           ON si.c_stk_code = p.c_stk_code
          AND si.c_trade_date = :report_date
    LEFT JOIN tb_dict_params d
           ON d.c_param_code = LEFT(si.c_citic_code, 6)
          AND d.c_param_type = '中信行业分类'
    WHERE p.c_report_date = :report_date
      AND p.c_style       = :style
      AND p.c_is_stat     = -1
      AND p.c_fd_code     IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes,
                             report_date=report_date,
                             style=date_to_style(report_date))


def _fetch_cb_holdings(doris: DorisConnector, fd_codes: list[str],
                       report_date: str) -> pd.DataFrame:
    """
    转股期转债（c_bd_type='2'）全量 + 普通债券（c_bd_type='1'）前5大
    同时拼正股代码、正股行业、信用评级
    """
    sql = """
    SELECT p.c_fd_code, p.c_bd_code, p.c_bd_name,
           p.c_bd_type, p.c_hold_value, p.c_nav_ratio,
           bb.c_credit_rating,
           bb.c_stk_code AS c_stk_code,
           d.c_param_name AS c_stk_industry
    FROM tb_fd_portfolio_bd p
    LEFT JOIN tb_bd_basic_info bb
           ON bb.c_bd_code = p.c_bd_code
          AND bb.c_bd_type IN ('可转换债券', '可交换债券', '可分离交易可转债')
    LEFT JOIN tb_stk_industry si
           ON si.c_stk_code = bb.c_stk_code
          AND si.c_trade_date = :report_date
    LEFT JOIN tb_dict_params d
           ON d.c_param_code = LEFT(si.c_citic_code, 6)
          AND d.c_param_type = '中信行业分类'
    WHERE p.c_report_date = :report_date
      AND p.c_style       = :style
      AND p.c_is_stat     = -1
      AND p.c_fd_code     IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes,
                             report_date=report_date,
                             style=date_to_style(report_date))


def _fetch_bd_style_tags(doris: DorisConnector, fd_codes: list[str]) -> pd.DataFrame:
    sql = """
    SELECT c_fd_code,
           c_bd_type_style, c_bd_type_timing,
           c_leverage_pref, c_leverage_timing,
           c_credit_pref, c_credit_timing,
           c_duration_pref, c_duration_timing,
           c_leverage_avg, c_duration_avg
    FROM tb_fd_tag_bd_style
    WHERE c_report_date = :report_date
      AND c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes, report_date=REPORT_DATE)


# ── 组装 Sheet ────────────────────────────────────────────────────


def _build_alloc_overview(universe: pd.DataFrame,
                          alloc_cur: pd.DataFrame,
                          alloc_prev: pd.DataFrame) -> pd.DataFrame:
    def rename_alloc(df, suffix):
        return df.rename(columns={
            'c_stk_total_ratio':     f'股票%({suffix})',
            'c_bd_convertible_ratio': f'转债%({suffix})',
            'c_stk_equity_ratio':    f'权益%({suffix})',
            'c_stk_hk_connect_ratio': f'港股通%({suffix})',
        })

    cur  = rename_alloc(alloc_cur, '本期')
    prev = rename_alloc(alloc_prev, '上期')

    df = universe[['c_fd_code', 'c_short_name', 'c_type2_name', 'c_company_name']].copy()
    df = df.merge(cur, on='c_fd_code', how='left')
    df = df.merge(prev[['c_fd_code'] + [c for c in prev.columns if c != 'c_fd_code']],
                  on='c_fd_code', how='left')
    return df.rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型', 'c_company_name': '基金公司',
    })


def _build_category_pos_trend(universe: pd.DataFrame,
                               alloc_multi: pd.DataFrame,
                               dates: list[str]) -> pd.DataFrame:
    """近4期各品类仓位中位数"""
    merged = alloc_multi.merge(
        universe[['c_fd_code', 'c_type2_name']], on='c_fd_code', how='inner'
    )
    rows = []
    for dt in dates:
        sub = merged[merged['c_report_date'].astype(str) == dt]
        for cat, grp in sub.groupby('c_type2_name'):
            rows.append({
                '报告期': dt,
                '二级类型': cat,
                '股票仓位中位数%': grp['c_stk_total_ratio'].median(),
                '转债仓位中位数%': grp['c_bd_convertible_ratio'].median(),
                '权益仓位中位数%': grp['c_stk_equity_ratio'].median(),
            })
    df = pd.DataFrame(rows)
    for col in ['股票仓位中位数%', '转债仓位中位数%', '权益仓位中位数%']:
        df[col] = df[col].round(2)
    return df.sort_values(['报告期', '二级类型']).reset_index(drop=True)


def _build_stk_detail(universe: pd.DataFrame, stk_df: pd.DataFrame) -> pd.DataFrame:
    df = stk_df.merge(universe[['c_fd_code', 'c_short_name', 'c_type2_name']],
                      on='c_fd_code', how='left')
    df['c_hold_value'] = (df['c_hold_value'] / 1e8).round(4)
    return df[[
        'c_fd_code', 'c_short_name', 'c_type2_name',
        'c_stk_code', 'c_stk_name', 'c_industry',
        'c_hold_value', 'c_nav_ratio',
    ]].rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型',
        'c_stk_code': '股票代码', 'c_stk_name': '股票名称',
        'c_industry': '中信一级行业',
        'c_hold_value': '持仓市值(亿)', 'c_nav_ratio': '占净值比%',
    })


def _build_industry_agg(universe: pd.DataFrame,
                        stk_cur: pd.DataFrame, stk_prev: pd.DataFrame) -> pd.DataFrame:
    """重仓股行业汇总（本期+上期+变化，分品类）"""
    def agg_by_industry(stk_df, univ, label):
        merged = stk_df.merge(univ[['c_fd_code', 'c_type2_name']], on='c_fd_code', how='left')
        merged['c_nav_ratio'] = pd.to_numeric(merged['c_nav_ratio'], errors='coerce')
        grp = merged.groupby(['c_type2_name', 'c_industry'])['c_nav_ratio'].sum().reset_index()
        # 行业占比 = 行业内所有基金持仓比例之和（描述市场整体集中度）
        grp.rename(columns={'c_nav_ratio': f'合计占净值比%({label})'}, inplace=True)
        return grp

    cur_agg  = agg_by_industry(stk_cur, universe, '本期')
    prev_agg = agg_by_industry(stk_prev, universe, '上期')
    merged   = cur_agg.merge(prev_agg, on=['c_type2_name', 'c_industry'], how='outer')
    merged['变化'] = (merged['合计占净值比%(本期)'] - merged['合计占净值比%(上期)']).round(2)
    for col in ['合计占净值比%(本期)', '合计占净值比%(上期)']:
        merged[col] = merged[col].round(2)
    merged.rename(columns={'c_type2_name': '二级类型', 'c_industry': '行业'}, inplace=True)
    return merged.sort_values(['二级类型', '合计占净值比%(本期)'], ascending=[True, False]).reset_index(drop=True)


def _build_top10_stk(universe: pd.DataFrame, stk_df: pd.DataFrame) -> pd.DataFrame:
    """各品类前十大重仓股（按持仓市值加总）"""
    merged = stk_df.merge(universe[['c_fd_code', 'c_type2_name']], on='c_fd_code', how='left')
    merged['c_hold_value'] = pd.to_numeric(merged['c_hold_value'], errors='coerce')
    grp = (
        merged.groupby(['c_type2_name', 'c_stk_code', 'c_industry'])
        ['c_hold_value'].sum()
        .reset_index()
    )
    # 加回股票名称（取最常见）
    names = stk_df.groupby('c_stk_code')['c_stk_name'].first().reset_index()
    grp = grp.merge(names, on='c_stk_code', how='left')
    grp['c_hold_value'] = (grp['c_hold_value'] / 1e8).round(4)

    frames = []
    for cat, sub in grp.groupby('c_type2_name'):
        top10 = sub.nlargest(10, 'c_hold_value').copy()
        top10.insert(0, '品类', cat)
        top10.insert(1, '品类内排名', range(1, len(top10) + 1))
        frames.append(top10)
    return pd.concat(frames, ignore_index=True).rename(columns={
        'c_type2_name': '二级类型', 'c_stk_code': '股票代码',
        'c_stk_name': '股票名称', 'c_industry': '行业',
        'c_hold_value': '合计持仓市值(亿)',
    })


def _build_cb_detail(universe: pd.DataFrame, cb_df: pd.DataFrame) -> pd.DataFrame:
    """转股期转债持仓明细（c_bd_type='2'）"""
    cb_sub = cb_df[cb_df['c_bd_type'] == '2'].copy()
    cb_sub = cb_sub.merge(universe[['c_fd_code', 'c_short_name', 'c_type2_name']],
                          on='c_fd_code', how='left')
    cb_sub['c_hold_value'] = (cb_sub['c_hold_value'] / 1e8).round(4)
    return cb_sub[[
        'c_fd_code', 'c_short_name', 'c_type2_name',
        'c_bd_code', 'c_bd_name', 'c_credit_rating',
        'c_stk_code', 'c_stk_industry',
        'c_hold_value', 'c_nav_ratio',
    ]].rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型',
        'c_bd_code': '转债代码', 'c_bd_name': '转债名称',
        'c_credit_rating': '信用评级',
        'c_stk_code': '正股代码', 'c_stk_industry': '正股行业',
        'c_hold_value': '持仓市值(亿)', 'c_nav_ratio': '占净值比%',
    }).sort_values(['基金代码', '占净值比%'], ascending=[True, False]).reset_index(drop=True)


def _build_cb_rating_dist(universe: pd.DataFrame,
                           cb_cur: pd.DataFrame, cb_prev: pd.DataFrame) -> pd.DataFrame:
    """转债评级分布（按持仓市值占比，本期+上期）"""
    def rating_agg(cb_df, label):
        cb_sub = cb_df[cb_df['c_bd_type'] == '2'].copy()
        cb_sub = cb_sub.merge(universe[['c_fd_code']], on='c_fd_code', how='inner')
        cb_sub['c_hold_value'] = pd.to_numeric(cb_sub['c_hold_value'], errors='coerce').fillna(0)
        total = cb_sub['c_hold_value'].sum()
        grp = cb_sub.groupby('c_credit_rating')['c_hold_value'].sum().reset_index()
        grp[f'持仓市值占比%({label})'] = (grp['c_hold_value'] / total * 100).round(2)
        return grp[['c_credit_rating', f'持仓市值占比%({label})']]

    cur_agg  = rating_agg(cb_cur, '本期')
    prev_agg = rating_agg(cb_prev, '上期')
    merged   = cur_agg.merge(prev_agg, on='c_credit_rating', how='outer').fillna(0)
    merged.rename(columns={'c_credit_rating': '信用评级'}, inplace=True)
    return merged.sort_values('持仓市值占比%(本期)', ascending=False).reset_index(drop=True)


def _build_cb_industry_dist(universe: pd.DataFrame,
                             cb_cur: pd.DataFrame, cb_prev: pd.DataFrame) -> pd.DataFrame:
    """转债行业分布（正股行业，本期+上期+变化）"""
    def ind_agg(cb_df, label):
        cb_sub = cb_df[cb_df['c_bd_type'] == '2'].copy()
        cb_sub = cb_sub.merge(universe[['c_fd_code']], on='c_fd_code', how='inner')
        cb_sub['c_nav_ratio'] = pd.to_numeric(cb_sub['c_nav_ratio'], errors='coerce')
        grp = cb_sub.groupby('c_stk_industry')['c_nav_ratio'].sum().reset_index()
        grp.rename(columns={'c_nav_ratio': f'合计占净值比%({label})'}, inplace=True)
        return grp

    cur_agg  = ind_agg(cb_cur, '本期')
    prev_agg = ind_agg(cb_prev, '上期')
    merged   = cur_agg.merge(prev_agg, on='c_stk_industry', how='outer').fillna(0)
    merged['变化'] = (merged['合计占净值比%(本期)'] - merged['合计占净值比%(上期)']).round(2)
    for col in ['合计占净值比%(本期)', '合计占净值比%(上期)']:
        merged[col] = merged[col].round(2)
    merged.rename(columns={'c_stk_industry': '正股行业'}, inplace=True)
    return merged.sort_values('合计占净值比%(本期)', ascending=False).reset_index(drop=True)


def _build_top20_cb(universe: pd.DataFrame, cb_df: pd.DataFrame) -> pd.DataFrame:
    """前20大重仓转债（按持仓市值汇总）"""
    cb_sub = cb_df[cb_df['c_bd_type'] == '2'].copy()
    cb_sub = cb_sub.merge(universe[['c_fd_code']], on='c_fd_code', how='inner')
    cb_sub['c_hold_value'] = pd.to_numeric(cb_sub['c_hold_value'], errors='coerce')
    grp = (
        cb_sub.groupby(['c_bd_code', 'c_bd_name', 'c_credit_rating', 'c_stk_code', 'c_stk_industry'])
        ['c_hold_value'].sum()
        .reset_index()
    )
    grp['持仓市值(亿)'] = (grp['c_hold_value'] / 1e8).round(4)
    top20 = grp.nlargest(20, '持仓市值(亿)').copy()
    top20.insert(0, '排名', range(1, len(top20) + 1))
    return top20[['排名', 'c_bd_code', 'c_bd_name', 'c_credit_rating',
                  'c_stk_code', 'c_stk_industry', '持仓市值(亿)']].rename(columns={
        'c_bd_code': '转债代码', 'c_bd_name': '转债名称',
        'c_credit_rating': '信用评级',
        'c_stk_code': '正股代码', 'c_stk_industry': '正股行业',
    }).reset_index(drop=True)


def _build_bd_style(universe: pd.DataFrame, tag_df: pd.DataFrame) -> pd.DataFrame:
    df = universe[['c_fd_code', 'c_short_name', 'c_type2_name', 'c_company_name']].merge(
        tag_df, on='c_fd_code', how='left'
    )
    return df.rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型', 'c_company_name': '基金公司',
        'c_bd_type_style': '券种风格', 'c_bd_type_timing': '券种择时',
        'c_leverage_pref': '杠杆偏好', 'c_leverage_timing': '杠杆择时',
        'c_credit_pref': '信用偏好', 'c_credit_timing': '信用择时',
        'c_duration_pref': '久期偏好', 'c_duration_timing': '久期择时',
        'c_leverage_avg': '杠杆率均值', 'c_duration_avg': '久期均值(年)',
    })


# ── 主流程 ────────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        logger.info("=== 模块五：持仓配置 ===")

        universe   = fetch_fi_universe(doris, REPORT_DATE)
        fd_codes   = universe['c_fd_code'].tolist()

        alloc_cur  = _fetch_asset_alloc(doris, REPORT_DATE)
        alloc_prev = _fetch_asset_alloc(doris, PREV_DATE)
        alloc_4qtr = _fetch_asset_alloc_multi(doris, RECENT_4_DATES)

        stk_cur    = _fetch_stk_holdings(doris, fd_codes, REPORT_DATE)
        stk_prev   = _fetch_stk_holdings(doris, fd_codes, PREV_DATE)

        cb_cur     = _fetch_cb_holdings(doris, fd_codes, REPORT_DATE)
        cb_prev    = _fetch_cb_holdings(doris, fd_codes, PREV_DATE)

        tag_df     = _fetch_bd_style_tags(doris, fd_codes)

    logger.info(f"本期重仓股记录：{len(stk_cur)}，转债持仓记录：{len(cb_cur)}")

    save_excel({
        '资产配置总览':         _build_alloc_overview(universe, alloc_cur, alloc_prev),
        '分品类仓位中位数(近4期)': _build_category_pos_trend(universe, alloc_4qtr, RECENT_4_DATES),
        '重仓股明细':           _build_stk_detail(universe, stk_cur),
        '重仓股行业汇总':        _build_industry_agg(universe, stk_cur, stk_prev),
        '前十大重仓股':          _build_top10_stk(universe, stk_cur),
        '转债持仓明细':          _build_cb_detail(universe, cb_cur),
        '转债评级分布':          _build_cb_rating_dist(universe, cb_cur, cb_prev),
        '转债行业分布':          _build_cb_industry_dist(universe, cb_cur, cb_prev),
        '前20大重仓转债':        _build_top20_cb(universe, cb_cur),
        '债券风格标签':          _build_bd_style(universe, tag_df),
    }, 'm5_holding.xlsx')
    logger.info("模块五完成")


if __name__ == '__main__':
    run()

"""
主动权益基金数据导出
输出列：
  基金基础数据.xlsx    : 基金代码 | 基金分类 | 基金名称 | 基金成立时间 | 现任基金经理
  个股持仓情况.xlsx    : 基金代码 | 报告期 | 股票代码 | 股票名称 | 股票占净值比例
  行业持仓数据.xlsx    : 基金代码 | 报告期 | 股票占净值比例 | [行业列...]
  基金净值数据_YYYY.xlsx : fundcode | tradedate | nav_adjusted（每月一个sheet）
"""
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))

from utils.db_connector import DorisConnector
from utils.common import generate_report_dates
from utils.log import setup_logger
from industry_theme_config import INDUSTRY_CONFIG, HK_PREFIX_THEME_MAPPING

logger = setup_logger(__name__)
ENV = 'dev'

# ============================================================
# 参数配置（每次只改这里）
# ============================================================
LATEST_REPORT_DATE = '2025-12-31'   # 最新报告期（季度末）
N_PERIODS          = 18             # 最近N个季度报告期（个股持仓用）
FUND_UNIVERSE_DATE = '2025-12-31'   # tb_fd_category 基金池快照日期
ESTAB_CUTOFF       = '2023-04-20'   # 成立满3年截止日
NAV_START_YEAR     = 2021           # 净值起始年份
NAV_END_DATE       = '2026-04-17'   # 净值截止日
# ============================================================

OUT_DIR = Path(__file__).parent / 'data'

# ── 行业映射（模块加载时一次性构建）──
_A_L1_MAP:  dict = {}   # A股申万前6位 → 一级行业名称
_HK_L1_MAP: dict = {}   # 港股港交所前6位 → 行业名称
_THEME_MAP: dict = {}   # 12位申万 or 港交所前6位 → 板块主题

for _ind_name, _items in INDUSTRY_CONFIG.items():
    for _item in _items:
        _code = _item['ind_code']
        _A_L1_MAP[_code[:6]] = _ind_name
        _THEME_MAP[_code] = _item['theme']
for _hk_code, _meta in HK_PREFIX_THEME_MAPPING.items():
    _HK_L1_MAP[_hk_code] = _meta['name']
    _THEME_MAP[_hk_code] = _meta['theme']

_ALL_A_IND  = list(INDUSTRY_CONFIG.keys())
_ALL_HK_IND = [v['name'] for v in HK_PREFIX_THEME_MAPPING.values()]


# ─────────────────────────────────────────────────────────
# 1. 基金列表
# ─────────────────────────────────────────────────────────

def _fetch_fund_list(doris: DorisConnector) -> pd.DataFrame:
    sql = """
    SELECT a.c_fd_code, a.c_short_name, a.c_estabdate, a.c_manager_name
    FROM tytdata.tb_fd_basic_info a
    JOIN tytdata.tb_fd_category b
        ON a.c_fd_code = b.c_fd_code
        AND b.c_report_date = :universe_date
    WHERE b.c_type2_code = '001001'
      AND a.c_estabdate <= :estab_cutoff
      AND a.c_terminate_date IS NULL
      AND (a.c_init_code = a.c_fd_code OR a.c_init_code IS NULL)
    ORDER BY a.c_fd_code
    """
    return doris.query(sql, universe_date=FUND_UNIVERSE_DATE, estab_cutoff=ESTAB_CUTOFF)


# ─────────────────────────────────────────────────────────
# 2. 全持仓 + 行业（半年报/年报，用于行业宽表和板块分类）
# ─────────────────────────────────────────────────────────

def _fetch_holdings_with_ind(doris: DorisConnector,
                             fund_codes: list,
                             semi_dates: list) -> pd.DataFrame:
    """
    查全持仓（c_style IN ('02','04')），JOIN申万行业（A股）和港交所行业（港股）。
    A股6位代码 → tb_stk_industry（日频，c_trade_date=报告期）
    港股5位代码 → tb_stk_industry_hk（静态快照）
    """
    sql = """
    SELECT p.c_fd_code,
           p.c_report_date,
           p.c_stk_code,
           p.c_nav_ratio,
           COALESCE(i.c_sw_code, hk.c_hkex_code) AS ind_code
    FROM tytdata.tb_fd_portfolio_stk p
    LEFT JOIN tytdata.tb_stk_industry i
           ON p.c_stk_code = i.c_stk_code
          AND i.c_trade_date = :report_date
    LEFT JOIN tytdata.tb_stk_industry_hk hk
           ON p.c_stk_code = hk.c_stk_code
    WHERE p.c_fd_code IN (:code_list)
      AND p.c_report_date = :report_date
      AND p.c_style IN ('02', '04')
    """
    results = []
    for rd in semi_dates:
        df = doris.query_batch(sql, fund_codes, report_date=rd)
        if not df.empty:
            results.append(df)
        logger.info(f"  全持仓+行业 {rd}: {len(df)} 行")
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


# ─────────────────────────────────────────────────────────
# 3. 总股票仓位（来自资产配置表）
# ─────────────────────────────────────────────────────────

def _fetch_stock_position(doris: DorisConnector,
                          fund_codes: list,
                          semi_dates: list) -> pd.DataFrame:
    """同一报告期可能有多条（c_style='02'/'05'或'04'/'06'），取 c_style 最小的一条。"""
    sql = """
    WITH ranked AS (
        SELECT c_fd_code, c_report_date, c_stk_total_ratio,
               ROW_NUMBER() OVER (
                   PARTITION BY c_fd_code, c_report_date
                   ORDER BY c_style
               ) AS rn
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_fd_code IN (:code_list)
          AND c_report_date = :report_date
    )
    SELECT c_fd_code, c_report_date, c_stk_total_ratio
    FROM ranked
    WHERE rn = 1
    """
    results = []
    for rd in semi_dates:
        df = doris.query_batch(sql, fund_codes, report_date=rd)
        if not df.empty:
            results.append(df)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


# ─────────────────────────────────────────────────────────
# 4. 行业持仓宽表
# ─────────────────────────────────────────────────────────

def _build_ind_pivot(holdings: pd.DataFrame,
                     stock_pos: pd.DataFrame) -> pd.DataFrame:
    df = holdings.copy()

    def _map_industry(ind_code):
        if pd.isna(ind_code):
            return None
        s = str(ind_code)
        return _A_L1_MAP.get(s[:6]) or _HK_L1_MAP.get(s[:6])

    df['industry'] = df['ind_code'].map(_map_industry)
    df = df.dropna(subset=['industry'])

    agg = (df.groupby(['c_fd_code', 'c_report_date', 'industry'])['c_nav_ratio']
             .sum()
             .reset_index())

    pivot = agg.pivot_table(
        index=['c_fd_code', 'c_report_date'],
        columns='industry',
        values='c_nav_ratio',
        fill_value=0,
    ).reset_index()
    pivot.columns.name = None

    result = stock_pos.merge(pivot, on=['c_fd_code', 'c_report_date'], how='left')

    for col in _ALL_A_IND + _ALL_HK_IND:
        if col not in result.columns:
            result[col] = 0

    ordered = (['c_fd_code', 'c_report_date', 'c_stk_total_ratio']
               + [c for c in _ALL_A_IND + _ALL_HK_IND if c in result.columns])
    result = result[ordered].rename(columns={
        'c_fd_code':          '基金代码',
        'c_report_date':      '报告期',
        'c_stk_total_ratio':  '股票占净值比例',
    })
    result['报告期']   = pd.to_datetime(result['报告期']).dt.strftime('%Y%m%d')
    result['基金代码'] = result['基金代码'] + '.OF'
    return result


# ─────────────────────────────────────────────────────────
# 5. 板块分类（跨期平均，生成"科技/消费/…"等标签）
# ─────────────────────────────────────────────────────────

def _classify_fund_theme(holdings: pd.DataFrame) -> pd.DataFrame:
    df = holdings.copy()

    def _map_theme(ind_code):
        if pd.isna(ind_code):
            return None
        s = str(ind_code)
        return _THEME_MAP.get(s) or _THEME_MAP.get(s[:6])

    df['theme'] = df['ind_code'].map(_map_theme)
    df = df.dropna(subset=['theme'])

    fund_total = df.groupby(['c_fd_code', 'c_report_date'])['c_nav_ratio'].sum()
    theme_sum  = (df.groupby(['c_fd_code', 'c_report_date', 'theme'])['c_nav_ratio']
                    .sum().reset_index())
    theme_sum['allocation'] = theme_sum.apply(
        lambda r: r['c_nav_ratio'] / fund_total.get(
            (r['c_fd_code'], r['c_report_date']), 1) * 100,
        axis=1,
    )

    avg = theme_sum.groupby(['c_fd_code', 'theme'])['allocation'].mean().reset_index()

    results = []
    for fund_code, g in avg.groupby('c_fd_code'):
        g = g.sort_values('allocation', ascending=False).reset_index(drop=True)
        t1, r1 = g.iloc[0]['theme'], g.iloc[0]['allocation']
        if r1 > 60:
            category = t1
        elif len(g) >= 2:
            t2, r2 = g.iloc[1]['theme'], g.iloc[1]['allocation']
            if r2 > 30 and (r1 + r2) > 80:
                category = f'{t1}_{t2}'
            elif (r1 - r2) > 20:
                category = f'全市场偏{t1}'
            else:
                category = '全市场'
        else:
            category = t1
        results.append({'c_fd_code': fund_code, '基金分类': category})

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────
# 6. 前十大持仓（季报口径）
# ─────────────────────────────────────────────────────────

def _add_exchange_suffix(code: str) -> str:
    code = str(code)
    if len(code) == 5:
        return code + '.HK'
    if code.startswith('6'):
        return code + '.SH'
    if code.startswith('8') or code.startswith('43'):
        return code + '.BJ'
    return code + '.SZ'


def _fetch_top10_holdings(doris: DorisConnector,
                          fund_codes: list,
                          all_dates: list) -> pd.DataFrame:
    sql = """
    SELECT p.c_fd_code,
           p.c_report_date,
           p.c_stk_code,
           COALESCE(a.c_stk_name, hk.c_stk_name) AS c_stk_name,
           p.c_nav_ratio
    FROM tytdata.tb_fd_portfolio_stk p
    LEFT JOIN tytdata.tb_stk_basic_info a
           ON p.c_stk_code = a.c_stk_code
    LEFT JOIN tytdata.tb_stk_basic_info_hk hk
           ON p.c_stk_code = hk.c_stk_code
    WHERE p.c_fd_code IN (:code_list)
      AND p.c_report_date = :report_date
      AND p.c_style IN ('01', '03', '05', '06')
    ORDER BY p.c_fd_code, p.c_nav_ratio DESC
    """
    results = []
    for rd in all_dates:
        df = doris.query_batch(sql, fund_codes, report_date=rd)
        if not df.empty:
            results.append(df)
        logger.info(f"  前十大持仓 {rd}: {len(df)} 行")
    if not results:
        return pd.DataFrame()

    df = pd.concat(results, ignore_index=True)
    df = df.rename(columns={
        'c_fd_code':     '基金代码',
        'c_report_date': '报告期',
        'c_stk_code':    '股票代码',
        'c_stk_name':    '股票名称',
        'c_nav_ratio':   '股票占净值比例',
    })
    df['报告期']   = pd.to_datetime(df['报告期']).dt.strftime('%Y%m%d')
    df['基金代码'] = df['基金代码'] + '.OF'
    df['股票代码'] = df['股票代码'].apply(_add_exchange_suffix)
    df = df[['基金代码', '报告期', '股票代码', '股票名称', '股票占净值比例']]
    return df


# ─────────────────────────────────────────────────────────
# 7. 净值（按年分文件，每月一个sheet）
# ─────────────────────────────────────────────────────────

def _fetch_and_save_nav(doris: DorisConnector, fund_codes: list) -> None:
    sql = """
    SELECT c_fd_code, c_trade_date, c_nav_adj
    FROM tytdata.tb_fd_nav_daily
    WHERE c_fd_code IN (:code_list)
      AND c_trade_date >= :begin_date
      AND c_trade_date <= :end_date
      AND c_is_trade = '1'
    ORDER BY c_fd_code, c_trade_date
    """
    end_year = int(NAV_END_DATE[:4])
    for year in range(NAV_START_YEAR, end_year + 1):
        begin_date = f'{year}-01-01'
        end_date   = min(f'{year}-12-31', NAV_END_DATE)

        logger.info(f"  净值 {year}年 ({begin_date} ~ {end_date})...")
        nav = doris.query_batch(sql, fund_codes, begin_date=begin_date, end_date=end_date)
        if nav.empty:
            continue

        nav = nav.rename(columns={
            'c_fd_code':    'fundcode',
            'c_trade_date': 'tradedate',
            'c_nav_adj':    'nav_adjusted',
        })
        nav['tradedate'] = pd.to_datetime(nav['tradedate']).dt.strftime('%Y%m%d')
        nav['fundcode']  = nav['fundcode'] + '.OF'

        filepath = OUT_DIR / f'基金净值数据_{year}.xlsx'
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for month in range(1, 13):
                m_str   = f'{month:02d}'
                m_df    = nav[nav['tradedate'].str[4:6] == m_str][
                              ['fundcode', 'tradedate', 'nav_adjusted']]
                if m_df.empty:
                    continue
                m_df.to_excel(writer, sheet_name=f'{month}月', index=False)

        logger.info(f"  → {filepath.name}（{len(nav)} 行）")


# ─────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────

def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_dates  = generate_report_dates(LATEST_REPORT_DATE, N_PERIODS)
    semi_dates = [d for d in all_dates if d[5:] in ('06-30', '12-31')]
    logger.info(f"报告期：全部{len(all_dates)}个，半年报/年报{len(semi_dates)}个")

    with DorisConnector(ENV) as doris:
        # ── 基金列表 ──
        logger.info("获取基金列表...")
        fund_df    = _fetch_fund_list(doris)
        fund_codes = fund_df['c_fd_code'].tolist()
        logger.info(f"基金数量: {len(fund_codes)}")

        # ── 全持仓 + 行业（半年/年报）──
        logger.info("获取全持仓+行业数据...")
        holdings = _fetch_holdings_with_ind(doris, fund_codes, semi_dates)

        # ── 总股票仓位 ──
        logger.info("获取总股票仓位...")
        stock_pos = _fetch_stock_position(doris, fund_codes, semi_dates)

        # ── 前十大持仓（全报告期）──
        logger.info("获取前十大持仓...")
        holdings10 = _fetch_top10_holdings(doris, fund_codes, all_dates)

        # ── 净值 ──
        logger.info("获取净值数据...")
        _fetch_and_save_nav(doris, fund_codes)

    # ── 行业持仓宽表 ──
    logger.info("构建行业持仓宽表...")
    ind_pivot = _build_ind_pivot(holdings, stock_pos)

    # ── 板块分类 ──
    logger.info("计算板块分类...")
    category_df = _classify_fund_theme(holdings)

    # ── 基金基础数据（合并分类）──
    fund_out = fund_df.merge(category_df, on='c_fd_code', how='left')
    fund_out['c_estabdate'] = pd.to_datetime(fund_out['c_estabdate']).dt.strftime('%Y/%m/%d')
    fund_out = fund_out.rename(columns={
        'c_fd_code':      '基金代码',
        'c_short_name':   '基金名称',
        'c_estabdate':    '基金成立时间',
        'c_manager_name': '现任基金经理',
    })
    fund_out = fund_out[['基金代码', '基金分类', '基金名称', '基金成立时间', '现任基金经理']]
    fund_out['基金代码'] = fund_out['基金代码'] + '.OF'

    # ── 写出 ──
    fund_out.to_excel(OUT_DIR / '基金基础数据.xlsx', index=False)
    logger.info(f"基金基础数据: {len(fund_out)} 行 → data/基金基础数据.xlsx")

    ind_pivot.to_excel(OUT_DIR / '行业持仓数据.xlsx', index=False)
    logger.info(f"行业持仓数据: {len(ind_pivot)} 行 → data/行业持仓数据.xlsx")

    holdings10.to_excel(OUT_DIR / '个股持仓情况.xlsx', index=False)
    logger.info(f"个股持仓情况: {len(holdings10)} 行 → data/个股持仓情况.xlsx")

    logger.info("全部完成")


if __name__ == '__main__':
    run()

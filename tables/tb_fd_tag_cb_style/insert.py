"""固收+基金转债投资风格标签生成

5维度: 组合构建、板块特征、交易特征、转债风格、正股风格
数据源: tb_fd_portfolio_bd / tb_bd_basic_info / tb_stk_industry
       tb_cb_analysis / Oracle BOND_CB_SWAPDETAIL (余额截面)
       tb_stk_risk_factor / tb_stk_barra_status
"""
import sys
from pathlib import Path


def _setup_path():
    """兼容本地和 DS 环境的路径适配"""
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

from dataclasses import dataclass
from functools import reduce
from typing import Dict, List

import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector, OracleConnector
from utils.common import generate_report_dates
from utils.log import setup_logger

logger = setup_logger(__name__)

# ============================================================
ENV = 'dev'
# ============================================================

# 中信一级行业(025) → 六大板块映射（同 tb_fd_tag_stk_region_sector）
SECTOR_MAP: Dict[str, str] = {
    "025001": "cycle",    "025002": "cycle",    "025003": "cycle",
    "025005": "cycle",    "025006": "cycle",    "025008": "cycle",
    "025025": "cycle",
    "025004": "mfg",      "025007": "mfg",      "025010": "mfg",
    "025011": "mfg",      "025012": "mfg",      "025013": "mfg",    "025030": "mfg",
    "025026": "tech",     "025027": "tech",     "025028": "tech",   "025029": "tech",
    "025009": "consumer", "025014": "consumer", "025015": "consumer",
    "025016": "consumer", "025017": "consumer", "025019": "consumer", "025020": "consumer",
    "025018": "pharma",
    "025021": "fin",      "025022": "fin",      "025023": "fin",    "025024": "fin",
}
SECTORS = ["cycle", "mfg", "tech", "consumer", "pharma", "fin"]
SECTOR_CN = {
    "cycle": "周期", "mfg": "中游制造", "tech": "科技",
    "consumer": "消费", "pharma": "医药", "fin": "金融地产",
}


@dataclass(frozen=True)
class CbStyleConfig:
    QUARTERLY_PERIODS: int = 8

    # 属性标签（平底溢价率阈值, %）
    FLOOR_PREM_DEBT: float = -20.0    # 平底溢价率 ≤ 此值计为偏债
    FLOOR_PREM_EQUITY: float = 20.0   # 平底溢价率 ≥ 此值计为偏股
    ATTR_DEBT_MIN: float = 50.0       # 偏债占比 > 50% → 偏债型
    ATTR_EQUITY_MIN: float = 30.0     # 偏股占比 > 30% → 偏股型（优先级低于偏债）

    # 股性/债性分位阈值（0~1，全市场分位）
    EQUITY_STRONG: float = 0.30
    EQUITY_WEAK: float = 0.70
    BOND_STRONG: float = 0.30
    BOND_WEAK: float = 0.70

    # 余额分位阈值
    BALANCE_HIGH: float = 0.70
    BALANCE_LOW: float = 0.30

    # 板块标签阈值
    SECTOR_TRACK_MIN: float = 50.0    # 赛道型：max板块权重 > 50%
    SECTOR_ROTATE_CHG: float = 20.0   # 轮动型：sector_chg ≥ 20%

    # 样本内分位阈值（集中度/交易/市值）
    HIGH_QUANTILE: float = 0.70
    LOW_QUANTILE: float = 0.30

    # 正股风格（样本内分位）
    GROWTH_QUANTILE: float = 0.67
    VALUE_QUANTILE: float = 0.33


CFG = CbStyleConfig()


# ============================================================
# 数据查询
# ============================================================

def _get_near_trade_dates(doris: DorisConnector, q_dates: List[str]) -> Dict[str, str]:
    """获取各季报期对应最近交易日（报告期非交易日时 Barra/转债估值无数据）"""
    sql = """
    SELECT c_date, c_max_trade_date
    FROM tytdata.tb_trade_calendar
    WHERE c_date IN (:code_list)
    """
    df = doris.query_batch(sql, code_list=q_dates)
    df['c_date'] = pd.to_datetime(df['c_date']).dt.strftime('%Y-%m-%d')
    df['c_max_trade_date'] = pd.to_datetime(df['c_max_trade_date']).dt.strftime('%Y-%m-%d')
    return dict(zip(df['c_date'], df['c_max_trade_date']))


def _get_fund_universe(doris: DorisConnector, report_date: str,
                       q_dates: List[str]) -> List[str]:
    """固收+(002)主代码基金，近8期 c_bd_convertible_ratio 均值 ≥ 1%"""
    sql_base = """
    SELECT DISTINCT c.c_fd_code
    FROM tytdata.tb_fd_category c
    JOIN tytdata.tb_fd_basic_info b ON c.c_fd_code = b.c_fd_code
    WHERE c.c_report_date = :report_date
      AND c.c_type1_code = '002'
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    """
    base = doris.query(sql_base, report_date=report_date)
    if base.empty:
        return []
    fund_codes = base['c_fd_code'].tolist()

    # 近8期季报转债投资占比均值（去重：同期取首个c_style）
    sql_ratio = """
    SELECT c_fd_code,
           AVG(IFNULL(c_bd_convertible_ratio, 0)) AS avg_cb_ratio
    FROM (
        SELECT c_fd_code, c_report_date, c_bd_convertible_ratio,
               ROW_NUMBER() OVER (PARTITION BY c_fd_code, c_report_date
                                  ORDER BY c_style) AS rn
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_fd_code IN (:code_list)
          AND c_report_date BETWEEN :start_date AND :end_date
          AND c_style IN ('01','03','05','06')
    ) t
    WHERE rn = 1
    GROUP BY c_fd_code
    """
    ratio_df = doris.query_batch(sql_ratio, code_list=fund_codes,
                                 start_date=q_dates[0], end_date=q_dates[-1])
    valid = ratio_df[ratio_df['avg_cb_ratio'] >= 1]['c_fd_code'].tolist()
    logger.info(f"固收+基金 {len(fund_codes)} 只 → 近8期CB均值≥1% 共 {len(valid)} 只")
    return valid


def _query_cb_holdings(doris: DorisConnector, fund_codes: List[str],
                       q_dates: List[str]) -> pd.DataFrame:
    """查询各季度CB持仓（转股期全量 + 前5大普通债中的未转股期可转债）"""
    # 转股期CB（c_bd_type='2'，季报全量披露）
    sql1 = """
    SELECT c_fd_code, c_bd_code, c_report_date,
           IFNULL(c_nav_ratio, 0) AS c_nav_ratio
    FROM tytdata.tb_fd_portfolio_bd
    WHERE c_fd_code IN (:code_list)
      AND c_report_date BETWEEN :start_date AND :end_date
      AND c_style IN ('01','03','05','06')
      AND c_bd_type = '2'
    """
    df1 = doris.query_batch(sql1, code_list=fund_codes,
                            start_date=q_dates[0], end_date=q_dates[-1])

    # 普通债TOP5中的未转股期可转债（JOIN tb_bd_basic_info 识别）
    sql2 = """
    SELECT p.c_fd_code, p.c_bd_code, p.c_report_date,
           IFNULL(p.c_nav_ratio, 0) AS c_nav_ratio
    FROM tytdata.tb_fd_portfolio_bd p
    JOIN tytdata.tb_bd_basic_info b ON p.c_bd_code = b.c_bd_code
    WHERE p.c_fd_code IN (:code_list)
      AND p.c_report_date BETWEEN :start_date AND :end_date
      AND p.c_style IN ('01','03','05','06')
      AND p.c_bd_type = '1'
      AND b.c_bd_type = '可转换债券'
    """
    df2 = doris.query_batch(sql2, code_list=fund_codes,
                            start_date=q_dates[0], end_date=q_dates[-1])

    df = pd.concat([df1, df2], ignore_index=True)
    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    target = pd.to_datetime(q_dates)
    df = df[df['c_report_date'].isin(target)].copy()
    logger.info(f"CB持仓明细 {len(df)} 条")
    return df


def _query_cb_meta(doris: DorisConnector, cb_codes: List[str]) -> pd.DataFrame:
    """获取CB正股代码（tb_bd_basic_info），用于行业/正股风格映射"""
    if not cb_codes:
        return pd.DataFrame(columns=['c_bd_code', 'c_stk_code'])
    sql = """
    SELECT c_bd_code, c_stk_code
    FROM tytdata.tb_bd_basic_info
    WHERE c_bd_code IN (:code_list)
      AND c_stk_code IS NOT NULL
    """
    return doris.query_batch(sql, code_list=cb_codes)


def _query_stk_industry(doris: DorisConnector, stk_codes: List[str],
                        trade_dates: List[str]) -> pd.DataFrame:
    """获取正股中信一级行业（日频快照），按各季报期近交易日查询"""
    if not stk_codes:
        return pd.DataFrame(columns=['c_stk_code', 'c_trade_date', 'c_ind_code'])
    sql = """
    SELECT c_stk_code, c_trade_date, c_ind_code
    FROM tytdata.tb_stk_industry
    WHERE c_stk_code IN (:code_list)
      AND c_trade_date = :d
    """
    dfs = []
    for td in trade_dates:
        df = doris.query_batch(sql, code_list=stk_codes, d=td)
        if not df.empty:
            df['c_trade_date'] = pd.to_datetime(df['c_trade_date']).dt.strftime('%Y-%m-%d')
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else \
        pd.DataFrame(columns=['c_stk_code', 'c_trade_date', 'c_ind_code'])


def _query_cb_valuation_mkt(doris: DorisConnector, trade_date: str) -> pd.DataFrame:
    """全市场CB溢价率截面（用于计算转股/纯债分位）"""
    sql = """
    SELECT c_bd_code, c_conv_prem_rate, c_straight_prem_rate, c_floor_prem_rate
    FROM tytdata.tb_cb_analysis
    WHERE c_trade_date = :d
      AND c_conv_prem_rate IS NOT NULL
      AND c_straight_prem_rate IS NOT NULL
    """
    return doris.query(sql, d=trade_date)


def _query_cb_balance_mkt(oracle: OracleConnector, trade_date: str) -> pd.DataFrame:
    """全市场CB余额截面（Oracle BOND_CB_SWAPDETAIL，单位转为亿元）"""
    sql = """
    SELECT BONDCODE AS c_bd_code,
           UNTRANSFER_AMT / 1e8 AS balance_bil
    FROM TYTFUND.BOND_CB_SWAPDETAIL
    WHERE TDATE = TO_DATE(:trade_date, 'YYYY-MM-DD')
      AND UNTRANSFER_AMT > 0
    """
    return oracle.query(sql, trade_date=trade_date)


def _query_stk_barra(doris: DorisConnector, trade_date: str) -> pd.DataFrame:
    """全市场A股流通市值（用于正股市值分位计算）"""
    sql = """
    SELECT c_stk_code, c_float_mv
    FROM tytdata.tb_stk_barra_status
    WHERE c_trade_date = :d
    """
    return doris.query(sql, d=trade_date)


def _query_stk_factors(doris: DorisConnector, trade_date: str,
                       stk_codes: List[str]) -> pd.DataFrame:
    """获取正股 Barra 因子宽表（VALUE/GROWTH/PROF）"""
    if not stk_codes:
        return pd.DataFrame(columns=['c_stk_code'])
    sql = """
    SELECT c_stk_code, c_factor_code, c_factor_value
    FROM tytdata.tb_stk_risk_factor
    WHERE c_trade_date = :d
      AND c_factor_code IN ('VALUE','GROWTH','PROF')
      AND c_stk_code IN (:code_list)
    """
    df = doris.query_batch(sql, code_list=stk_codes, d=trade_date)
    if df.empty:
        return pd.DataFrame(columns=['c_stk_code'])
    pivot = df.pivot(index='c_stk_code', columns='c_factor_code',
                     values='c_factor_value')
    pivot.columns.name = None
    return pivot.reset_index()


# ============================================================
# 数据富化
# ============================================================

def _enrich_holdings(holdings: pd.DataFrame, cb_meta: pd.DataFrame,
                     industry: pd.DataFrame,
                     trade_date_map: Dict[str, str]) -> pd.DataFrame:
    """CB持仓补充正股代码、行业代码、板块"""
    df = holdings.copy()
    df['trade_date'] = df['c_report_date'].dt.strftime('%Y-%m-%d').map(trade_date_map)
    df = df.merge(cb_meta[['c_bd_code', 'c_stk_code']], on='c_bd_code', how='left')

    if not industry.empty:
        ind = industry.rename(columns={'c_trade_date': 'trade_date'})
        df = df.merge(ind[['c_stk_code', 'trade_date', 'c_ind_code']],
                      on=['c_stk_code', 'trade_date'], how='left')
    else:
        df['c_ind_code'] = None

    df['sector'] = df['c_ind_code'].map(SECTOR_MAP)
    return df


# ============================================================
# 维度1：组合构建（个券/行业/板块集中度）
# ============================================================

def _concentration_one_period(grp: pd.DataFrame) -> pd.Series:
    """单个(基金, 报告期)的集中度指标"""
    total = grp['c_nav_ratio'].sum()
    if total <= 0:
        return pd.Series({k: np.nan for k in
                          ['top10_ratio', 'hhi', 'ind_top5_ratio', 'ind_hhi',
                           'sector_top1_ratio', 'sector_hhi']})

    w = grp['c_nav_ratio'] / total
    top10_ratio = float(w.nlargest(10).sum() * 100)
    hhi = float((w ** 2).sum())

    ind_grp = grp.dropna(subset=['c_ind_code'])
    if not ind_grp.empty:
        ind_tot = ind_grp['c_nav_ratio'].sum()
        ind_w = ind_grp.groupby('c_ind_code')['c_nav_ratio'].sum() / ind_tot
        ind_top5 = float(ind_w.nlargest(5).sum() * 100)
        ind_hhi = float((ind_w ** 2).sum())
    else:
        ind_top5, ind_hhi = np.nan, np.nan

    sec_grp = grp.dropna(subset=['sector'])
    if not sec_grp.empty:
        sec_tot = sec_grp['c_nav_ratio'].sum()
        sec_w = sec_grp.groupby('sector')['c_nav_ratio'].sum() / sec_tot
        sec_top1 = float(sec_w.max() * 100)
        sec_hhi = float((sec_w ** 2).sum())
    else:
        sec_top1, sec_hhi = np.nan, np.nan

    return pd.Series({'top10_ratio': top10_ratio, 'hhi': hhi,
                      'ind_top5_ratio': ind_top5, 'ind_hhi': ind_hhi,
                      'sector_top1_ratio': sec_top1, 'sector_hhi': sec_hhi})


def _calc_portfolio_construction(enriched: pd.DataFrame) -> pd.DataFrame:
    """近8期均值 → 样本内分位 → 集中度标签"""
    metrics = (enriched.groupby(['c_fd_code', 'c_report_date'])
               .apply(_concentration_one_period, include_groups=False)
               .reset_index())

    cols = ['top10_ratio', 'hhi', 'ind_top5_ratio', 'ind_hhi', 'sector_top1_ratio', 'sector_hhi']
    avg = metrics.groupby('c_fd_code')[cols].mean().round(6).reset_index()

    def _rank(s: pd.Series) -> pd.Series:
        return s.rank(pct=True, na_option='keep')

    avg['cb_score'] = (_rank(avg['top10_ratio']) + _rank(avg['hhi'])) / 2
    avg['ind_score'] = (_rank(avg['ind_top5_ratio']) + _rank(avg['ind_hhi'])) / 2
    avg['sec_score'] = (_rank(avg['sector_top1_ratio']) + _rank(avg['sector_hhi'])) / 2

    def _tag(score: pd.Series) -> pd.Series:
        return pd.cut(score, bins=[-np.inf, CFG.LOW_QUANTILE, CFG.HIGH_QUANTILE, np.inf],
                      labels=['分散', '均衡', '集中']).astype(str)

    avg['c_cb_concent_tag'] = _tag(avg['cb_score'])
    avg['c_cb_ind_concent_tag'] = _tag(avg['ind_score'])
    avg['c_cb_sector_concent_tag'] = _tag(avg['sec_score'])
    avg['sec_score'] = avg['sec_score'].round(4)

    return avg.rename(columns={
        'top10_ratio': 'c_cb_top10_ratio', 'hhi': 'c_cb_hhi',
        'ind_top5_ratio': 'c_cb_ind_top5_ratio', 'ind_hhi': 'c_cb_ind_hhi',
        'sector_top1_ratio': 'c_cb_sector_top1_ratio', 'sector_hhi': 'c_cb_sector_hhi',
        'sec_score': 'c_cb_sector_concent_score',
    })[['c_fd_code',
        'c_cb_top10_ratio', 'c_cb_hhi', 'c_cb_concent_tag',
        'c_cb_ind_top5_ratio', 'c_cb_ind_hhi', 'c_cb_ind_concent_tag',
        'c_cb_sector_top1_ratio', 'c_cb_sector_hhi',
        'c_cb_sector_concent_score', 'c_cb_sector_concent_tag']]


# ============================================================
# 维度2：板块特征与偏好
# ============================================================

def _calc_sector_features(enriched: pd.DataFrame) -> pd.DataFrame:
    """六大板块权重均值 + 变动指标 + 板块标签"""
    df = enriched.dropna(subset=['sector']).copy()
    if df.empty:
        return pd.DataFrame(columns=['c_fd_code'] +
                            [f'c_cb_sector_{s}' for s in SECTORS] +
                            ['c_cb_sector_chg', 'c_cb_sector_tag', 'c_cb_sector_pref'])

    # 各期各基金各板块权重（占有板块归属的CB总仓位的比例）
    total = df.groupby(['c_fd_code', 'c_report_date'])['c_nav_ratio'].sum().reset_index()
    total.columns = ['c_fd_code', 'c_report_date', 'total']
    sec_sum = (df.groupby(['c_fd_code', 'c_report_date', 'sector'])['c_nav_ratio']
               .sum().reset_index())
    sec_sum = sec_sum.merge(total, on=['c_fd_code', 'c_report_date'])
    sec_sum['weight'] = np.where(sec_sum['total'] > 0,
                                 sec_sum['c_nav_ratio'] / sec_sum['total'] * 100, 0.0)

    wide = (sec_sum.pivot_table(index=['c_fd_code', 'c_report_date'],
                                columns='sector', values='weight',
                                aggfunc='sum', fill_value=0)
            .reset_index())
    for s in SECTORS:
        if s not in wide.columns:
            wide[s] = 0.0

    avg_w = (wide.groupby('c_fd_code')[SECTORS].mean().round(4).reset_index()
             .rename(columns={s: f'c_cb_sector_{s}' for s in SECTORS}))

    # 变动指标：各板块绝对变化的板块均值加权（同 tb_fd_tag_stk_region_sector）
    def _weighted_chg(g: pd.DataFrame) -> float:
        g = g.sort_values('c_report_date')
        avg = g[SECTORS].mean()
        abs_chg = g[SECTORS].diff().abs().mean().fillna(0)
        denom = avg.sum()
        return float((avg * abs_chg).sum() / denom) if denom > 0 else 0.0

    chg = (wide.groupby('c_fd_code')
           .apply(_weighted_chg, include_groups=False)
           .round(4).rename('c_cb_sector_chg'))
    result = avg_w.join(chg, on='c_fd_code')

    def _assign_tag(row: pd.Series) -> pd.Series:
        max_w = row[[f'c_cb_sector_{s}' for s in SECTORS]].max()
        chg_v = row['c_cb_sector_chg']
        if chg_v >= CFG.SECTOR_ROTATE_CHG and max_w * (1 - chg_v / 100) <= CFG.SECTOR_TRACK_MIN:
            return pd.Series({'c_cb_sector_tag': '轮动型', 'c_cb_sector_pref': ''})
        if max_w > CFG.SECTOR_TRACK_MIN:
            best = row[[f'c_cb_sector_{s}' for s in SECTORS]].idxmax()
            pref = SECTOR_CN[best.replace('c_cb_sector_', '')]
            return pd.Series({'c_cb_sector_tag': '赛道型', 'c_cb_sector_pref': pref})
        return pd.Series({'c_cb_sector_tag': '均衡型', 'c_cb_sector_pref': ''})

    tags = result.apply(_assign_tag, axis=1, result_type='expand')
    return pd.concat([result, tags], axis=1)


# ============================================================
# 维度3：交易特征（留存率/换手率/持有期）
# ============================================================

def _calc_trade_characteristics(holdings: pd.DataFrame) -> pd.DataFrame:
    """近7期相邻季报的留存率、换手率，以及持有期均值"""
    results = []
    for fd, grp in holdings.groupby('c_fd_code'):
        grp = grp.sort_values('c_report_date')
        dates = sorted(grp['c_report_date'].unique())
        if len(dates) < 2:
            continue

        retain_rates, turnover_rates = [], []
        for i in range(1, len(dates)):
            prev = grp[grp['c_report_date'] == dates[i - 1]]
            curr = grp[grp['c_report_date'] == dates[i]]
            if prev.empty or curr.empty:
                retain_rates.append(0.0 if prev.empty else 0.0)
                turnover_rates.append(100.0)
                continue
            retained = set(prev['c_bd_code']) & set(curr['c_bd_code'])
            retain_rates.append(len(retained) / len(prev) * 100)
            prev_w = prev['c_nav_ratio'].sum()
            if prev_w > 0:
                retained_w = sum(
                    min(prev.loc[prev['c_bd_code'] == b, 'c_nav_ratio'].iloc[0],
                        curr.loc[curr['c_bd_code'] == b, 'c_nav_ratio'].iloc[0])
                    for b in retained
                )
                turnover_rates.append((1 - retained_w / prev_w) * 100)
            else:
                turnover_rates.append(100.0)

        # 持有期：净值占比>0时记为持有，收集所有连续持有段（同研究脚本逻辑）
        holding_periods = []
        for bd, bd_grp in grp[grp['c_nav_ratio'] > 0].groupby('c_bd_code'):
            held = set(bd_grp['c_report_date'])
            cur = 0
            for d in sorted(dates):
                if d in held:
                    cur += 1
                else:
                    if cur > 0:
                        holding_periods.append(cur)
                    cur = 0
            if cur > 0:
                holding_periods.append(cur)

        results.append({
            'c_fd_code': fd,
            'c_cb_retain_rate': float(np.mean(retain_rates)),
            'c_cb_turnover_rate': float(np.mean(turnover_rates)),
            'c_cb_hold_period': float(np.mean(holding_periods)) if holding_periods else np.nan,
        })

    if not results:
        return pd.DataFrame(columns=['c_fd_code', 'c_cb_retain_rate',
                                     'c_cb_turnover_rate', 'c_cb_hold_period',
                                     'c_cb_trade_score', 'c_cb_trade_tag'])
    df = pd.DataFrame(results)

    retain_pct = df['c_cb_retain_rate'].rank(pct=True, na_option='keep')
    # 换手越低 → 复合分位越高（偏长期持有）
    turnover_pct = 1 - df['c_cb_turnover_rate'].rank(pct=True, na_option='keep')
    hold_pct = df['c_cb_hold_period'].rank(pct=True, na_option='keep')
    df['c_cb_trade_score'] = ((retain_pct + turnover_pct + hold_pct) / 3).round(4)
    df['c_cb_trade_tag'] = pd.cut(
        df['c_cb_trade_score'],
        bins=[-np.inf, CFG.LOW_QUANTILE, CFG.HIGH_QUANTILE, np.inf],
        labels=['频繁交易', '持有适中', '长期持有']
    ).astype(str)
    return df[['c_fd_code', 'c_cb_retain_rate', 'c_cb_turnover_rate', 'c_cb_hold_period',
               'c_cb_trade_score', 'c_cb_trade_tag']]


# ============================================================
# 维度4：转债风格（属性/股性/债性/余额）
# ============================================================

def _calc_cb_style(holdings: pd.DataFrame,
                   mkt_val_by_date: Dict[str, pd.DataFrame],
                   mkt_bal_by_date: Dict[str, pd.DataFrame],
                   trade_date_map: Dict[str, str]) -> pd.DataFrame:
    """全市场CB分位 → 基金持仓加权均值 → 近8期均值 → 标签"""
    all_periods: List[dict] = []

    for rd in sorted(holdings['c_report_date'].unique()):
        td = trade_date_map.get(rd.strftime('%Y-%m-%d'), '')
        period_h = holdings[holdings['c_report_date'] == rd].copy()
        if period_h.empty or not td:
            continue

        mkt_val = mkt_val_by_date.get(td, pd.DataFrame())
        if mkt_val.empty:
            continue

        mkt_val = mkt_val.copy()
        mkt_val['conv_prem_pct'] = mkt_val['c_conv_prem_rate'].rank(pct=True)
        mkt_val['bond_prem_pct'] = mkt_val['c_straight_prem_rate'].rank(pct=True)

        mkt_bal = mkt_bal_by_date.get(td, pd.DataFrame())
        if not mkt_bal.empty:
            mkt_bal = mkt_bal.copy()
            mkt_bal['balance_pct'] = mkt_bal['balance_bil'].rank(pct=True)
            mkt_val = mkt_val.merge(mkt_bal[['c_bd_code', 'balance_pct']],
                                    on='c_bd_code', how='left')
        else:
            mkt_val['balance_pct'] = np.nan

        period_h = period_h.merge(
            mkt_val[['c_bd_code', 'conv_prem_pct', 'bond_prem_pct',
                      'c_floor_prem_rate', 'balance_pct']],
            on='c_bd_code', how='inner'
        )
        if period_h.empty:
            continue

        for fd, fh in period_h.groupby('c_fd_code'):
            tot = fh['c_nav_ratio'].sum()
            if tot <= 0:
                continue
            fw = fh['c_nav_ratio'] / tot
            valid_bal = fh['balance_pct'].dropna()
            all_periods.append({
                'c_fd_code': fd,
                'debt_like': float((fh['c_floor_prem_rate'] <= CFG.FLOOR_PREM_DEBT).mean() * 100),
                'equity_like': float((fh['c_floor_prem_rate'] >= CFG.FLOOR_PREM_EQUITY).mean() * 100),
                'equity_score': float((fw * fh['conv_prem_pct']).sum()),
                'bond_score': float((fw * fh['bond_prem_pct']).sum()),
                'balance_score': float(
                    (fh.loc[valid_bal.index, 'c_nav_ratio'] /
                     fh.loc[valid_bal.index, 'c_nav_ratio'].sum() *
                     valid_bal).sum()
                ) if not valid_bal.empty else np.nan,
            })

    if not all_periods:
        return pd.DataFrame(columns=['c_fd_code'])

    per_df = pd.DataFrame(all_periods)
    avg = (per_df.groupby('c_fd_code')
           [['debt_like', 'equity_like', 'equity_score', 'bond_score', 'balance_score']]
           .mean().round(4).reset_index())

    # 属性标签（偏债 > 偏股 优先级）
    avg['c_cb_attr_tag'] = '均衡'
    avg.loc[avg['debt_like'] > CFG.ATTR_DEBT_MIN, 'c_cb_attr_tag'] = '偏债'
    avg.loc[(avg['c_cb_attr_tag'] == '均衡') &
            (avg['equity_like'] > CFG.ATTR_EQUITY_MIN), 'c_cb_attr_tag'] = '偏股'

    # 股性/债性标签（全市场绝对分位阈值）
    avg['c_cb_equity_tag'] = '股性中等'
    avg.loc[avg['equity_score'] <= CFG.EQUITY_STRONG, 'c_cb_equity_tag'] = '股性强'
    avg.loc[avg['equity_score'] > CFG.EQUITY_WEAK, 'c_cb_equity_tag'] = '股性弱'

    avg['c_cb_bond_tag'] = '债性中等'
    avg.loc[avg['bond_score'] <= CFG.BOND_STRONG, 'c_cb_bond_tag'] = '债性强'
    avg.loc[avg['bond_score'] > CFG.BOND_WEAK, 'c_cb_bond_tag'] = '债性弱'

    avg['c_cb_balance_tag'] = '中余额'
    avg.loc[avg['balance_score'] >= CFG.BALANCE_HIGH, 'c_cb_balance_tag'] = '高余额'
    avg.loc[avg['balance_score'] < CFG.BALANCE_LOW, 'c_cb_balance_tag'] = '低余额'

    return avg.rename(columns={
        'debt_like': 'c_cb_debt_like_ratio', 'equity_like': 'c_cb_equity_like_ratio',
        'equity_score': 'c_cb_equity_score', 'bond_score': 'c_cb_bond_score',
        'balance_score': 'c_cb_balance_score',
    })[['c_fd_code', 'c_cb_debt_like_ratio', 'c_cb_equity_like_ratio', 'c_cb_attr_tag',
        'c_cb_equity_score', 'c_cb_equity_tag',
        'c_cb_bond_score', 'c_cb_bond_tag',
        'c_cb_balance_score', 'c_cb_balance_tag']]


# ============================================================
# 维度5：正股风格（市值/价值/成长/盈利）
# ============================================================

def _calc_stk_style(holdings: pd.DataFrame, cb_meta: pd.DataFrame,
                    factor_by_date: Dict[str, pd.DataFrame],
                    barra_by_date: Dict[str, pd.DataFrame],
                    trade_date_map: Dict[str, str]) -> pd.DataFrame:
    """正股 Barra 因子加权暴露 + 市值分位 → 近8期均值 → 标签"""
    h = holdings.merge(cb_meta[['c_bd_code', 'c_stk_code']], on='c_bd_code', how='inner')
    h = h.dropna(subset=['c_stk_code'])
    if h.empty:
        return pd.DataFrame(columns=['c_fd_code'])

    all_periods: List[dict] = []
    for rd in sorted(h['c_report_date'].unique()):
        td = trade_date_map.get(rd.strftime('%Y-%m-%d'), '')
        if not td:
            continue
        period_h = h[h['c_report_date'] == rd].copy()
        barra = barra_by_date.get(td, pd.DataFrame())
        factors = factor_by_date.get(td, pd.DataFrame())
        if barra.empty or factors.empty:
            continue

        barra = barra.copy()
        barra['mktcap_pct'] = barra['c_float_mv'].rank(pct=True)
        period_h = period_h.merge(barra[['c_stk_code', 'mktcap_pct']], on='c_stk_code', how='left')
        period_h = period_h.merge(factors, on='c_stk_code', how='left')

        for fd, fh in period_h.groupby('c_fd_code'):
            tot = fh['c_nav_ratio'].sum()
            if tot <= 0:
                continue
            fw = fh['c_nav_ratio'] / tot
            record = {'c_fd_code': fd}
            # 市值分位（全市场）
            valid = fh[['mktcap_pct', 'c_nav_ratio']].dropna(subset=['mktcap_pct'])
            record['mktcap_score'] = float(
                (valid['c_nav_ratio'] / valid['c_nav_ratio'].sum() * valid['mktcap_pct']).sum()
            ) if not valid.empty else np.nan
            # 因子加权暴露
            for fac in ['VALUE', 'GROWTH', 'PROF']:
                if fac not in fh.columns:
                    record[fac.lower()] = np.nan
                    continue
                valid_f = fh[['c_nav_ratio', fac]].dropna(subset=[fac])
                record[fac.lower()] = float(
                    (valid_f['c_nav_ratio'] / valid_f['c_nav_ratio'].sum() * valid_f[fac]).sum()
                ) if not valid_f.empty else np.nan
            all_periods.append(record)

    if not all_periods:
        return pd.DataFrame(columns=['c_fd_code'])

    per_df = pd.DataFrame(all_periods)
    avg = (per_df.groupby('c_fd_code')[['mktcap_score', 'value', 'growth', 'prof']]
           .mean().round(4).reset_index())
    avg['c_stk_style_score'] = (avg['growth'] - avg['value']).round(4)

    # 市值标签（全市场分位均值 → 绝对阈值）
    avg['c_stk_mktcap_tag'] = '中盘'
    avg.loc[avg['mktcap_score'] >= CFG.HIGH_QUANTILE, 'c_stk_mktcap_tag'] = '大盘'
    avg.loc[avg['mktcap_score'] < CFG.LOW_QUANTILE, 'c_stk_mktcap_tag'] = '小盘'

    # 正股风格标签（样本内分位）
    style_pct = avg['c_stk_style_score'].rank(pct=True, na_option='keep')
    avg['c_stk_style_tag'] = '均衡'
    avg.loc[style_pct >= CFG.GROWTH_QUANTILE, 'c_stk_style_tag'] = '成长'
    avg.loc[style_pct <= CFG.VALUE_QUANTILE, 'c_stk_style_tag'] = '价值'

    return avg.rename(columns={
        'mktcap_score': 'c_stk_mktcap_score',
        'value': 'c_stk_value_score',
        'growth': 'c_stk_growth_score',
        'prof': 'c_stk_profit_score',
    })[['c_fd_code', 'c_stk_mktcap_score', 'c_stk_mktcap_tag',
        'c_stk_value_score', 'c_stk_growth_score', 'c_stk_profit_score',
        'c_stk_style_score', 'c_stk_style_tag']]


# ============================================================
# 主入口
# ============================================================

def run(report_date: str) -> None:
    """主入口，report_date 为报告期如 '2025-12-31'"""
    logger.info(f"开始生成 {report_date} 转债投资风格标签")
    q_dates = generate_report_dates(report_date, CFG.QUARTERLY_PERIODS)

    with DorisConnector(ENV) as doris:
        trade_date_map = _get_near_trade_dates(doris, q_dates)
        trade_dates = list(trade_date_map.values())

        fund_codes = _get_fund_universe(doris, report_date, q_dates)
        if not fund_codes:
            logger.warning("无符合条件的基金，跳过")
            return

        holdings = _query_cb_holdings(doris, fund_codes, q_dates)
        if holdings.empty:
            logger.warning("无CB持仓数据，跳过")
            return

        cb_codes = holdings['c_bd_code'].unique().tolist()
        cb_meta = _query_cb_meta(doris, cb_codes)
        stk_codes = cb_meta['c_stk_code'].dropna().unique().tolist()

        industry = _query_stk_industry(doris, stk_codes, trade_dates)
        logger.info(f"行业数据 {len(industry)} 条")

        # 转债估值截面（全市场，每个近交易日）
        mkt_val_by_date: Dict[str, pd.DataFrame] = {}
        for td in trade_dates:
            mkt_val_by_date[td] = _query_cb_valuation_mkt(doris, td)

        # 正股 Barra 因子（每个近交易日）
        barra_by_date: Dict[str, pd.DataFrame] = {}
        factor_by_date: Dict[str, pd.DataFrame] = {}
        for td in trade_dates:
            barra_by_date[td] = _query_stk_barra(doris, td)
            factor_by_date[td] = _query_stk_factors(doris, td, stk_codes)

    # Oracle: CB余额截面（不占用 Doris 连接）
    mkt_bal_by_date: Dict[str, pd.DataFrame] = {}
    with OracleConnector(ENV) as oracle:
        for td in trade_dates:
            mkt_bal_by_date[td] = _query_cb_balance_mkt(oracle, td)

    # 富化持仓（补正股代码/行业/板块）
    enriched = _enrich_holdings(holdings, cb_meta, industry, trade_date_map)

    # 各维度计算
    concent_df = _calc_portfolio_construction(enriched)
    logger.info(f"维度1 组合构建: {len(concent_df)} 只")

    sector_df = _calc_sector_features(enriched)
    logger.info(f"维度2 板块特征: {len(sector_df)} 只")

    trade_df = _calc_trade_characteristics(holdings)
    logger.info(f"维度3 交易特征: {len(trade_df)} 只")

    cb_style_df = _calc_cb_style(holdings, mkt_val_by_date, mkt_bal_by_date, trade_date_map)
    logger.info(f"维度4 转债风格: {len(cb_style_df)} 只")

    stk_style_df = _calc_stk_style(holdings, cb_meta, factor_by_date, barra_by_date, trade_date_map)
    logger.info(f"维度5 正股风格: {len(stk_style_df)} 只")

    # 组装（outer merge: 各维度覆盖范围可能不同）
    dfs = [concent_df, sector_df, trade_df, cb_style_df, stk_style_df]
    result = reduce(lambda l, r: pd.merge(l, r, on='c_fd_code', how='outer'), dfs)
    result['c_report_date'] = pd.to_datetime(report_date)

    numeric_cols = result.select_dtypes(include='number').columns
    result[numeric_cols] = result[numeric_cols].round(4)

    logger.info(f"生成标签 {len(result)} 条")

    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_tag_cb_style', result)
    logger.info("写入完成")


if __name__ == '__main__':
    from utils.common import should_run, ReportFreq
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
        if ok:
            run(report_date)
    else:
        # 历史补数：2016-12-31 起，共 38 期季报
        for dt in generate_report_dates('2026-03-31', 38):
            run(dt)

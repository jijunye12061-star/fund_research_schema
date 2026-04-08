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
import time
from functools import partial, reduce

import numpy as np
import pandas as pd
import yaml
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates
from utils.log import setup_logger, step

logger = setup_logger(__name__)
_step = partial(step, logger)

ENV = 'dev'

_YAML_PATH = Path(__file__).resolve().parent.parent / 'tb_fd_tag_stk_region_sector' / 'sector_mapping.yaml'
with open(_YAML_PATH, 'r', encoding='utf-8') as f:
    _cfg = yaml.safe_load(f)
SECTOR_MAP = _cfg['mapping']
SECTORS = list(_cfg['sectors'].keys())

OUTPUT_COLS = [
    'c_report_date', 'c_fd_code',
    'c_sector_hhi', 'c_ind_hhi', 'c_ind_top5_ratio', 'c_ind_concent_rank', 'c_top10_ratio',
    'c_sector_concent_tag', 'c_ind_concent_tag', 'c_stk_concent_tag',
    'c_active_sector', 'c_active_ind', 'c_active_sector_rank', 'c_active_ind_rank', 'c_active_tag',
    'c_new_stk_ratio', 'c_new_stk_tag',
    'c_crowd_score', 'c_crowd_internal_score', 'c_crowd_tag',
    'c_buy_timing_score', 'c_buy_timing_tag',
    'c_sell_timing_score', 'c_sell_timing_tag',
    'c_turnover_avg', 'c_turnover_tag',
    'c_heavy_retain_rate', 'c_heavy_turnover', 'c_heavy_hold_period',
    'c_heavy_trade_rank', 'c_heavy_trade_tag',
]


# ==================== 数据查询 ====================

def _get_fund_types(doris: DorisConnector, report_date: str) -> pd.DataFrame:
    """权益+固收加+混合（001/002/004），仅主代码，返回(c_fd_code, c_type1_code)用于分类型排名"""
    sql = """
    SELECT DISTINCT c.c_fd_code, c.c_type1_code
    FROM tytdata.tb_fd_category c
    JOIN tytdata.tb_fd_basic_info b ON c.c_fd_code = b.c_fd_code
    WHERE c.c_type1_code IN ('001', '002', '004')
      AND c.c_report_date = :report_date
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    """
    return doris.query(sql, report_date=report_date)


def _get_trade_date(doris: DorisConnector, report_date: str) -> str:
    """报告期→对应最近交易日"""
    sql = """
    SELECT c_max_trade_date FROM tytdata.tb_trade_calendar
    WHERE c_date = :d
    """
    df = doris.query(sql, d=report_date)
    return str(df.iloc[0, 0])


def _query_ind_weight(doris: DorisConnector, fund_codes: list[str],
                      periods: list[str]) -> pd.DataFrame:
    """查询近4期半年报行业权重"""
    sql = """
    SELECT c_fd_code, c_report_date, c_ind_code, c_weight
    FROM tytdata.tb_fd_ind_weight
    WHERE c_fd_code IN (:code_list)
      AND c_report_date BETWEEN :start_date AND :end_date
    """
    df = doris.query_batch(sql, code_list=fund_codes,
                           start_date=periods[0], end_date=periods[-1])
    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    return df


def _query_heavy_stk(doris: DorisConnector, fund_codes: list[str],
                     periods: list[str]) -> pd.DataFrame:
    """查询近8期季报重仓股（前10大持股）
    c_style: 01=一季报, 03=三季报, 05=半年报重仓, 06=年报重仓"""
    sql = """
    WITH ranked AS (
        SELECT c_fd_code, c_report_date, c_stk_code, c_nav_ratio,
               ROW_NUMBER() OVER (
                   PARTITION BY c_fd_code, c_report_date, c_stk_code ORDER BY c_style
               ) AS rn
        FROM tytdata.tb_fd_portfolio_stk
        WHERE c_fd_code IN (:code_list)
          AND c_report_date BETWEEN :start_date AND :end_date
          AND c_style IN ('01','03','05','06')
          AND c_nav_ratio > 0
    )
    SELECT c_fd_code, c_report_date, c_stk_code, c_nav_ratio
    FROM ranked WHERE rn = 1
    """
    df = doris.query_batch(sql, code_list=fund_codes,
                           start_date=periods[0], end_date=periods[-1])
    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    return df


def _query_full_stk(doris: DorisConnector, fund_codes: list[str],
                    periods: list[str]) -> pd.DataFrame:
    """查询近多期半年报全持仓（用于top10和持股扩新）
    c_style: 02=半年报, 04=年报"""
    sql = """
    WITH ranked AS (
        SELECT c_fd_code, c_report_date, c_stk_code, c_nav_ratio,
               ROW_NUMBER() OVER (
                   PARTITION BY c_fd_code, c_report_date, c_stk_code ORDER BY c_style
               ) AS rn
        FROM tytdata.tb_fd_portfolio_stk
        WHERE c_fd_code IN (:code_list)
          AND c_report_date BETWEEN :start_date AND :end_date
          AND c_style IN ('02','04')
          AND c_nav_ratio > 0
    )
    SELECT c_fd_code, c_report_date, c_stk_code, c_nav_ratio
    FROM ranked WHERE rn = 1
    """
    df = doris.query_batch(sql, code_list=fund_codes,
                           start_date=periods[0], end_date=periods[-1])
    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    return df


def _query_benchmark(doris: DorisConnector, report_dates: list[str]) -> dict[str, pd.DataFrame]:
    """查询中证800各期行业/板块权重，返回 {report_date: DataFrame(c_ind_code, bm_ind_w, bm_sector_w)}"""
    result = {}
    for rd in report_dates:
        td = _get_trade_date(doris, rd)

        sql_idx = """
        SELECT c_stk_code, c_weight
        FROM tytdata.tb_idx_weight
        WHERE c_idx_code = '000906' AND c_trade_date = :td
        """
        idx_df = doris.query(sql_idx, td=td)

        sql_ind = """
        SELECT c_stk_code, SUBSTR(c_citic_code, 1, 6) AS c_ind_code
        FROM tytdata.tb_stk_industry
        WHERE c_trade_date = :td
        """
        ind_df = doris.query(sql_ind, td=td)

        merged = idx_df.merge(ind_df, on='c_stk_code', how='left')
        merged['sector'] = merged['c_ind_code'].map(SECTOR_MAP)
        bm = merged.groupby('c_ind_code').agg(
            bm_ind_w=('c_weight', 'sum'),
            sector=('sector', 'first')
        ).reset_index()
        result[rd] = bm
    return result


# ==================== 组合构建（集中度） ====================

def _calc_sector_hhi(ind_df: pd.DataFrame) -> pd.DataFrame:
    """板块HHI：行业权重→板块聚合→归一化→HHI，近4期半年报均值"""
    df = ind_df.copy()
    df['sector'] = df['c_ind_code'].map(SECTOR_MAP)
    df = df.dropna(subset=['sector'])
    sector_w = (df.groupby(['c_fd_code', 'c_report_date', 'sector'])['c_weight']
                  .sum().reset_index())

    def _hhi(g: pd.DataFrame) -> float:
        total = g['c_weight'].sum()
        if total <= 0:
            return np.nan
        w = g['c_weight'] / total
        return float((w ** 2).sum())

    hhi_per_period = (sector_w.groupby(['c_fd_code', 'c_report_date'])
                               .apply(_hhi, include_groups=False)
                               .reset_index(name='hhi'))
    return (hhi_per_period.groupby('c_fd_code')['hhi']
                          .mean().round(4).rename('c_sector_hhi').reset_index())


def _calc_ind_concentration(ind_df: pd.DataFrame) -> pd.DataFrame:
    """行业HHI和前5大行业权重，近4期半年报均值"""
    def _per_period(g: pd.DataFrame) -> pd.Series:
        total = g['c_weight'].sum()
        if total <= 0:
            return pd.Series({'hhi': np.nan, 'top5': np.nan})
        w = g['c_weight'] / total * 100
        hhi = float((w ** 2).sum() / (w.sum() ** 2))
        top5 = float(w.nlargest(5).sum())
        return pd.Series({'hhi': hhi, 'top5': top5})

    per_period = (ind_df.groupby(['c_fd_code', 'c_report_date'])
                        .apply(_per_period, include_groups=False)
                        .reset_index())
    avg = per_period.groupby('c_fd_code')[['hhi', 'top5']].mean().round(4).reset_index()
    return avg.rename(columns={'hhi': 'c_ind_hhi', 'top5': 'c_ind_top5_ratio'})


def _calc_top10_ratio(heavy_df: pd.DataFrame) -> pd.DataFrame:
    """前10大持股权重（季报重仓股权重之和），近8期季报均值"""
    per_period = (heavy_df.groupby(['c_fd_code', 'c_report_date'])['c_nav_ratio']
                          .sum().reset_index(name='top10'))
    return (per_period.groupby('c_fd_code')['top10']
                      .mean().round(4).rename('c_top10_ratio').reset_index())


# ==================== 主动管理 ====================

def _calc_active_deviation(ind_df: pd.DataFrame,
                           benchmark: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """计算主动板块偏离和主动行业偏离（板块内行业加权）"""
    records = []
    for rd, bm in benchmark.items():
        rd_ts = pd.Timestamp(rd)
        period_ind = ind_df[ind_df['c_report_date'] == rd_ts]
        if period_ind.empty:
            continue

        bm_sector = bm.groupby('sector')['bm_ind_w'].sum()
        bm_sector = bm_sector / bm_sector.sum() * 100

        # 预计算 bm 各板块内行业归一化权重（期内固定，不随基金变化）
        bm_inds_by_sector: dict[str, pd.Series] = {}
        for s, grp in bm.groupby('sector'):
            s_inds = grp.set_index('c_ind_code')['bm_ind_w']
            bm_inds_by_sector[s] = s_inds / s_inds.sum() * 100 if s_inds.sum() > 0 else s_inds

        for fd, fdf in period_ind.groupby('c_fd_code'):
            fund_total = fdf['c_weight'].sum()
            if fund_total <= 0:
                continue

            # 基金板块权重（归一化到100%）
            fdf = fdf.copy()
            fdf['sector'] = fdf['c_ind_code'].map(SECTOR_MAP)
            fdf = fdf.dropna(subset=['sector'])
            fund_sector = fdf.groupby('sector')['c_weight'].sum() / fund_total * 100

            # 板块偏离
            all_sectors = set(fund_sector.index) | set(bm_sector.index)
            sector_dev = np.mean([abs(fund_sector.get(s, 0) - bm_sector.get(s, 0))
                                  for s in all_sectors])

            # 预计算该基金各板块内行业归一化权重
            fund_inds_by_sector: dict[str, pd.Series] = {}
            for s, grp in fdf.groupby('sector'):
                s_inds = grp.set_index('c_ind_code')['c_weight']
                fund_inds_by_sector[s] = s_inds / s_inds.sum() * 100 if s_inds.sum() > 0 else s_inds

            # 行业偏离（板块内部）
            weighted_ind_dev = 0.0
            sector_weight_sum = 0.0
            for s in all_sectors:
                fund_s_w = fund_sector.get(s, 0)
                bm_s_w = bm_sector.get(s, 0)
                if fund_s_w <= 0 and bm_s_w <= 0:
                    continue

                fund_inds_norm = fund_inds_by_sector.get(s, pd.Series(dtype=float))
                bm_inds_norm = bm_inds_by_sector.get(s, pd.Series(dtype=float))

                all_inds = set(fund_inds_norm.index) | set(bm_inds_norm.index)
                ind_dev = np.mean([abs(fund_inds_norm.get(i, 0) - bm_inds_norm.get(i, 0))
                                   for i in all_inds])
                weighted_ind_dev += fund_s_w * ind_dev
                sector_weight_sum += fund_s_w

            active_ind = weighted_ind_dev / sector_weight_sum if sector_weight_sum > 0 else 0.0
            records.append({
                'c_fd_code': fd,
                'c_report_date': rd_ts,
                'active_sector': sector_dev,
                'active_ind': active_ind,
            })

    if not records:
        return pd.DataFrame(columns=['c_fd_code', 'c_active_sector', 'c_active_ind'])

    df = pd.DataFrame(records)
    avg = df.groupby('c_fd_code')[['active_sector', 'active_ind']].mean().round(4).reset_index()
    return avg.rename(columns={'active_sector': 'c_active_sector', 'active_ind': 'c_active_ind'})


def _calc_new_stk_ratio(full_df: pd.DataFrame, report_date: str) -> pd.DataFrame:
    """持股扩新：T期全持仓中未出现在T-1~T-3期的合计权重
    仅当 report_date 为半年报期（06-30/12-31）时计算"""
    if report_date[5:] not in ('06-30', '12-31'):
        return pd.DataFrame(columns=['c_fd_code', 'c_new_stk_ratio', 'c_new_stk_tag'])

    rd_ts = pd.Timestamp(report_date)
    t_df = full_df[full_df['c_report_date'] == rd_ts]
    hist_df = full_df[full_df['c_report_date'] < rd_ts]

    # 预先按基金分组历史持仓，避免循环内重复过滤整个 hist_df
    hist_stk_by_fd = hist_df.groupby('c_fd_code')['c_stk_code'].agg(set)

    records = []
    for fd, t_group in t_df.groupby('c_fd_code'):
        hist_stk = hist_stk_by_fd.get(fd, set())
        new_stk = t_group[~t_group['c_stk_code'].isin(hist_stk)]
        total = t_group['c_nav_ratio'].sum()
        ratio = float(new_stk['c_nav_ratio'].sum() / total * 100) if total > 0 else 0.0
        tag = '积极' if ratio >= 50 else ('适中' if ratio >= 20 else '保守')
        records.append({'c_fd_code': fd, 'c_new_stk_ratio': round(ratio, 4), 'c_new_stk_tag': tag})

    return pd.DataFrame(records)


# ==================== 交易特征 ====================

def _calc_heavy_trade(heavy_df: pd.DataFrame) -> pd.DataFrame:
    """重仓股留存率、换手率、持有期（近8期季报）"""
    records = []
    for fd, fdf in heavy_df.groupby('c_fd_code'):
        fdf = fdf.sort_values('c_report_date')
        periods = fdf['c_report_date'].unique()
        if len(periods) < 2:
            continue

        # 预计算每期的持仓集合和子DataFrame，避免内层循环重复过滤
        period_stk = {p: set(fdf.loc[fdf['c_report_date'] == p, 'c_stk_code']) for p in periods}
        period_df  = {p: fdf[fdf['c_report_date'] == p] for p in periods}

        retain_rates, turnover_rates = [], []
        for i in range(1, len(periods)):
            prev_stk = period_stk[periods[i - 1]]
            curr_stk = period_stk[periods[i]]
            retained = prev_stk & curr_stk

            retain_rates.append(len(retained) / len(prev_stk) * 100 if prev_stk else np.nan)

            prev_total_w = period_df[periods[i - 1]]['c_nav_ratio'].sum()
            retained_w = period_df[periods[i]].loc[
                period_df[periods[i]]['c_stk_code'].isin(retained), 'c_nav_ratio'
            ].sum()
            turnover_rates.append(
                (1 - retained_w / prev_total_w) * 100 if prev_total_w > 0 else np.nan
            )

        # 持有期：当前期重仓股各自连续持有多少期（O(1) 集合查找）
        curr_stk = period_stk[periods[-1]]
        hold_periods = []
        for stk in curr_stk:
            count = 0
            for p in reversed(periods):
                if stk in period_stk[p]:
                    count += 1
                else:
                    break
            hold_periods.append(count)

        records.append({
            'c_fd_code': fd,
            'c_heavy_retain_rate': round(np.nanmean(retain_rates), 4) if retain_rates else np.nan,
            'c_heavy_turnover': round(np.nanmean(turnover_rates), 4) if turnover_rates else np.nan,
            'c_heavy_hold_period': round(np.mean(hold_periods), 4) if hold_periods else np.nan,
        })

    return pd.DataFrame(records)


# ==================== 标签合成 ====================

def _merge_types(result: pd.DataFrame, fund_types: pd.DataFrame) -> pd.DataFrame:
    """合并类型信息，确保每基金只有一个类型"""
    types = fund_types[['c_fd_code', 'c_type1_code']].drop_duplicates('c_fd_code')
    return result.merge(types, on='c_fd_code', how='left')


def _type_quantile_tag(df: pd.DataFrame, val_col: str, tag_col: str,
                       result: pd.DataFrame) -> None:
    """按基金类型计算70%/30%分位，打集中/均衡/分散标签，写入 result（原地）"""
    q30 = df.groupby('c_type1_code')[val_col].transform(lambda x: x.quantile(0.3))
    q70 = df.groupby('c_type1_code')[val_col].transform(lambda x: x.quantile(0.7))
    tags = np.where(df[val_col] >= q70, '集中',
           np.where(df[val_col] <= q30, '分散', '均衡'))
    result[tag_col] = np.where(df[val_col].isna(), None, tags)


def _assign_concentration_tags(result: pd.DataFrame, fund_types: pd.DataFrame) -> None:
    """按基金类型分位打集中度标签，并计算行业集中度复合排名（原地修改）"""
    df = _merge_types(result, fund_types)

    # 行业集中度复合排名：HHI排名 + top5排名 等权
    rank_hhi = df.groupby('c_type1_code')['c_ind_hhi'].rank(pct=True, na_option='keep')
    rank_top5 = df.groupby('c_type1_code')['c_ind_top5_ratio'].rank(pct=True, na_option='keep')
    df['_ind_concent_rank'] = (rank_hhi + rank_top5) / 2
    result['c_ind_concent_rank'] = df['_ind_concent_rank'].round(4)

    _type_quantile_tag(df, 'c_sector_hhi', 'c_sector_concent_tag', result)
    _type_quantile_tag(df, '_ind_concent_rank', 'c_ind_concent_tag', result)
    _type_quantile_tag(df, 'c_top10_ratio', 'c_stk_concent_tag', result)


def _assign_active_tags(result: pd.DataFrame, fund_types: pd.DataFrame) -> None:
    """按基金类型分位计算主动偏离排名，打主动配置标签（原地修改）"""
    df = _merge_types(result, fund_types)

    result['c_active_sector_rank'] = (
        df.groupby('c_type1_code')['c_active_sector']
          .rank(pct=True, na_option='keep').round(4)
          .reindex(result.index).values
    )
    result['c_active_ind_rank'] = (
        df.groupby('c_type1_code')['c_active_ind']
          .rank(pct=True, na_option='keep').round(4)
          .reindex(result.index).values
    )

    sr = result['c_active_sector_rank']
    ir = result['c_active_ind_rank']
    result['c_active_tag'] = np.where(
        sr.isna() | ir.isna(), '',
        np.where(sr >= 0.7, np.where(ir >= 0.7, '主动配置', '主动板块配置'),
                 np.where(ir >= 0.7, '主动行业配置', ''))
    )


def _assign_trade_tags(result: pd.DataFrame, fund_types: pd.DataFrame) -> None:
    """按基金类型分位打重仓交易标签（原地修改）"""
    df = _merge_types(result, fund_types)

    retain_rank = df.groupby('c_type1_code')['c_heavy_retain_rate'].rank(pct=True, na_option='keep')
    # 换手率高=偏短期 → 降序排名（值越大排名越低）
    turnover_rank = df.groupby('c_type1_code')['c_heavy_turnover'].rank(
        pct=True, na_option='keep', ascending=False
    )
    period_rank = df.groupby('c_type1_code')['c_heavy_hold_period'].rank(pct=True, na_option='keep')

    df['_composite'] = (retain_rank + turnover_rank + period_rank) / 3
    result['c_heavy_trade_rank'] = df['_composite'].round(4).reindex(result.index).values

    q30 = df.groupby('c_type1_code')['_composite'].transform(lambda x: x.quantile(0.3))
    q70 = df.groupby('c_type1_code')['_composite'].transform(lambda x: x.quantile(0.7))
    tags = np.where(df['_composite'] >= q70, '偏长期持有',
           np.where(df['_composite'] <= q30, '偏短期交易', '持有期适中'))
    result['c_heavy_trade_tag'] = np.where(df['_composite'].isna(), None, tags)


# ==================== 换手率 ====================

def _calc_turnover(doris: DorisConnector, fund_codes: list[str],
                   report_date: str) -> pd.DataFrame:
    """查 tb_fd_turnover 近4期半年报，计算换手率均值（前向填充到季报期）"""
    all_semi = [d for d in generate_report_dates(report_date, 16)
                if d[5:] in ('06-30', '12-31')]
    semi_date = all_semi[-1]  # 最近半年报期（≤report_date）
    semi_4 = [d for d in generate_report_dates(semi_date, 8)
              if d[5:] in ('06-30', '12-31')][:4]

    sql = """
    SELECT c_fd_code, c_report_date, c_turnover_rate
    FROM tytdata.tb_fd_turnover
    WHERE c_fd_code IN (:code_list)
      AND c_report_date BETWEEN :start_date AND :end_date
    """
    df = doris.query_batch(sql, code_list=fund_codes,
                           start_date=semi_4[0], end_date=semi_4[-1])
    if df.empty:
        return pd.DataFrame(columns=['c_fd_code', 'c_turnover_avg'])

    avg = df.groupby('c_fd_code')['c_turnover_rate'].mean()
    return (avg / 100).round(4).rename('c_turnover_avg').reset_index()


def _assign_turnover_tag(result: pd.DataFrame, fund_types: pd.DataFrame) -> None:
    """按基金类型70%/30%分位打换手率标签（原地修改）"""
    df = _merge_types(result, fund_types)
    q70 = df.groupby('c_type1_code')['c_turnover_avg'].transform(lambda x: x.quantile(0.7))
    q30 = df.groupby('c_type1_code')['c_turnover_avg'].transform(lambda x: x.quantile(0.3))
    tags = np.where(df['c_turnover_avg'] >= q70, '高换手',
           np.where(df['c_turnover_avg'] <= q30, '低换手', '中换手'))
    result['c_turnover_tag'] = np.where(df['c_turnover_avg'].isna(), None, tags)


# ==================== 抱团度 ====================

def _query_crowd_scores(doris: DorisConnector, semi_date: str) -> pd.DataFrame:
    """查询个股抱团度得分（全市场+各公司）"""
    sql = """
    SELECT c_company_code, c_stk_code, c_crowd_score
    FROM tytdata.tb_stk_crowding_score
    WHERE c_report_date = :d
    """
    return doris.query(sql, d=semi_date)


def _query_holdings_for_crowd(doris: DorisConnector, fund_codes: list[str],
                               semi_date: str) -> pd.DataFrame:
    """查询半年报全持仓（用于抱团度加权聚合）"""
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
    return doris.query_batch(sql, code_list=fund_codes, report_date=semi_date)


def _get_company_map(doris: DorisConnector, fund_codes: list[str]) -> pd.DataFrame:
    """查询基金→公司代码映射"""
    sql = """
    SELECT c_fd_code, c_company_code
    FROM tytdata.tb_fd_basic_info
    WHERE c_fd_code IN (:code_list)
      AND c_company_code IS NOT NULL
    """
    return doris.query_batch(sql, code_list=fund_codes)


def _calc_crowd_mkt(holdings: pd.DataFrame, crowd_df: pd.DataFrame) -> pd.DataFrame:
    """全市场抱团度 = 持仓市值加权的 crowd_score 均值（MKT口径）"""
    mkt = crowd_df[crowd_df['c_company_code'] == 'MKT'][['c_stk_code', 'c_crowd_score']]
    df = holdings.merge(mkt, on='c_stk_code', how='inner')
    df['wt_score'] = df['c_hold_value'] * df['c_crowd_score']
    g = df.groupby('c_fd_code').agg(wt=('wt_score', 'sum'), w=('c_hold_value', 'sum'))
    return (g['wt'] / g['w']).round(4).rename('c_crowd_score').reset_index()


def _calc_crowd_internal(holdings: pd.DataFrame, company_map: pd.DataFrame,
                          crowd_df: pd.DataFrame) -> pd.DataFrame:
    """同公司抱团度 = 持仓市值加权的公司维度 crowd_score 均值"""
    co_crowd = crowd_df[crowd_df['c_company_code'] != 'MKT'][
        ['c_company_code', 'c_stk_code', 'c_crowd_score']]
    df = holdings.merge(company_map, on='c_fd_code', how='inner')
    df = df.merge(co_crowd, on=['c_company_code', 'c_stk_code'], how='inner')
    df['wt_score'] = df['c_hold_value'] * df['c_crowd_score']
    g = df.groupby('c_fd_code').agg(wt=('wt_score', 'sum'), w=('c_hold_value', 'sum'))
    return (g['wt'] / g['w']).round(4).rename('c_crowd_internal_score').reset_index()


def _calc_crowd_scores(doris: DorisConnector, fund_codes: list[str],
                       report_date: str) -> pd.DataFrame:
    """计算基金级全市场和同公司抱团度（季报期前向填充最近半年报）"""
    # reversed() 确保取最近的半年报期，而非最早的
    semi_date = next(d for d in reversed(generate_report_dates(report_date, 16))
                     if d[5:] in ('06-30', '12-31'))

    crowd_df = _query_crowd_scores(doris, semi_date)
    holdings = _query_holdings_for_crowd(doris, fund_codes, semi_date)
    company_map = _get_company_map(doris, fund_codes)

    mkt = _calc_crowd_mkt(holdings, crowd_df)
    internal = _calc_crowd_internal(holdings, company_map, crowd_df)
    return mkt.merge(internal, on='c_fd_code', how='outer')


# ==================== 买卖时机 ====================

def _query_stk_cum_returns(doris: DorisConnector, stk_codes: list[str],
                            start_td: str, end_td: str) -> pd.DataFrame:
    """股票在 (start_td, end_td] 区间的累计收益率（小数）"""
    sql = """
    SELECT c_stk_code,
           EXP(SUM(LN(1 + GREATEST(c_pct_chg, -99.0) / 100))) - 1 AS cum_ret
    FROM tytdata.tb_stk_quote_daily
    WHERE c_stk_code IN (:code_list)
      AND c_trade_date > :start_td
      AND c_trade_date <= :end_td
    GROUP BY c_stk_code
    """
    return doris.query_batch(sql, code_list=stk_codes, start_td=start_td, end_td=end_td)


def _query_fund_period_ret(doris: DorisConnector, fund_codes: list[str],
                            start_td: str, end_td: str) -> pd.DataFrame:
    """基金在 (start_td, end_td] 的区间收益率（小数），从 c_nav_adj 计算"""
    sql_end = """
    SELECT c_fd_code, c_nav_adj AS nav_end
    FROM tytdata.tb_fd_nav_daily
    WHERE c_fd_code IN (:code_list) AND c_trade_date = :td
    """
    sql_start = """
    SELECT c_fd_code, c_nav_adj AS nav_start
    FROM tytdata.tb_fd_nav_daily
    WHERE c_fd_code IN (:code_list) AND c_trade_date = :td
    """
    df_end = doris.query_batch(sql_end, code_list=fund_codes, td=end_td)
    df_start = doris.query_batch(sql_start, code_list=fund_codes, td=start_td)
    merged = df_end.merge(df_start, on='c_fd_code', how='inner')
    merged['fund_ret'] = merged['nav_end'] / merged['nav_start'] - 1
    return merged[['c_fd_code', 'fund_ret']]


def _query_equity_ratio(doris: DorisConnector, fund_codes: list[str],
                         report_date: str) -> pd.DataFrame:
    """基金在报告期的股票仓位（小数）"""
    sql = """
    SELECT c_fd_code, MAX(c_stk_total_ratio) / 100 AS equity_ratio
    FROM tytdata.tb_fd_asset_allocation
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style IN ('02', '04')
    GROUP BY c_fd_code
    """
    return doris.query_batch(sql, code_list=fund_codes, report_date=report_date)


def _calc_port_rets(holdings: pd.DataFrame, stk_rets: pd.DataFrame) -> pd.DataFrame:
    """持仓股票按 c_nav_ratio 归一化加权的收益率"""
    df = holdings.merge(stk_rets, on='c_stk_code', how='inner')
    df['wt_ret'] = df['c_nav_ratio'] * df['cum_ret']
    g = df.groupby('c_fd_code').agg(wt=('wt_ret', 'sum'), w=('c_nav_ratio', 'sum'))
    return (g['wt'] / g['w'].replace(0.0, np.nan)).rename('port_ret').reset_index()


def _calc_timing_scores(doris: DorisConnector, fund_codes: list[str],
                         report_date: str) -> pd.DataFrame:
    """买入/卖出时机超额均值(%)

    买入超额(T) = R_持仓组合(T-1→T) × 股票仓位(T-1) − R_基金(T-1→T)，近4期均值
    卖出超额(T) = R_持仓组合(T→T+1) × 股票仓位(T) − R_基金(T→T+1)，近3期均值（T-3~T-1，避免未来信息）
    """
    all_semi = [d for d in generate_report_dates(report_date, 16)
                if d[5:] in ('06-30', '12-31')]
    semi = all_semi[-1]

    # 需要5个连续半年报期：[T-4, T-3, T-2, T-1, T]
    semi_5 = [d for d in generate_report_dates(semi, 10)
              if d[5:] in ('06-30', '12-31')][:5]
    if len(semi_5) < 5:
        return pd.DataFrame(columns=['c_fd_code', 'c_buy_timing_score', 'c_sell_timing_score'])

    # 一次性拉全部持仓
    all_holdings = _query_full_stk(doris, fund_codes, semi_5)
    all_holdings['c_report_date'] = pd.to_datetime(all_holdings['c_report_date'])

    # 缓存交易日（报告期→实际交易日）
    trade_dates = {d: _get_trade_date(doris, d) for d in semi_5}

    buy_records, sell_records = [], []

    # 买入时机：4个区间（semi_5[0→1], [1→2], [2→3], [3→4]）
    for i in range(1, 5):
        t_prev, t = semi_5[i - 1], semi_5[i]
        td_prev, td_t = trade_dates[t_prev], trade_dates[t]
        holdings_t = all_holdings[all_holdings['c_report_date'] == pd.Timestamp(t)]
        if holdings_t.empty:
            continue
        stk_rets = _query_stk_cum_returns(doris, holdings_t['c_stk_code'].unique().tolist(), td_prev, td_t)
        port_rets = _calc_port_rets(holdings_t, stk_rets)
        fund_rets = _query_fund_period_ret(doris, fund_codes, td_prev, td_t)
        eq_ratio = _query_equity_ratio(doris, fund_codes, t_prev)
        df = (port_rets.merge(fund_rets, on='c_fd_code', how='inner')
                       .merge(eq_ratio, on='c_fd_code', how='inner'))
        df['excess'] = df['port_ret'] * df['equity_ratio'] - df['fund_ret']
        buy_records.append(df[['c_fd_code', 'excess']])

    # 卖出时机：3个区间（semi_5[1→2], [2→3], [3→4]），不含最新期 [4→?] 避免未来信息
    for i in range(1, 4):
        t, t_next = semi_5[i], semi_5[i + 1]
        td_t, td_next = trade_dates[t], trade_dates[t_next]
        holdings_t = all_holdings[all_holdings['c_report_date'] == pd.Timestamp(t)]
        if holdings_t.empty:
            continue
        stk_rets = _query_stk_cum_returns(doris, holdings_t['c_stk_code'].unique().tolist(), td_t, td_next)
        port_rets = _calc_port_rets(holdings_t, stk_rets)
        fund_rets = _query_fund_period_ret(doris, fund_codes, td_t, td_next)
        eq_ratio = _query_equity_ratio(doris, fund_codes, t)
        df = (port_rets.merge(fund_rets, on='c_fd_code', how='inner')
                       .merge(eq_ratio, on='c_fd_code', how='inner'))
        df['excess'] = df['port_ret'] * df['equity_ratio'] - df['fund_ret']
        sell_records.append(df[['c_fd_code', 'excess']])

    def _avg(records: list, col: str) -> pd.DataFrame:
        if not records:
            return pd.DataFrame(columns=['c_fd_code', col])
        return (pd.concat(records, ignore_index=True)
                  .groupby('c_fd_code')['excess'].mean()
                  .mul(100).round(4).rename(col).reset_index())

    return _avg(buy_records, 'c_buy_timing_score').merge(
        _avg(sell_records, 'c_sell_timing_score'), on='c_fd_code', how='outer'
    )


def _assign_timing_tags(result: pd.DataFrame) -> None:
    """买入/卖出时机标签：绝对0轴阈值（原地修改）"""
    result['c_buy_timing_tag'] = np.where(
        result['c_buy_timing_score'].isna(), None,
        np.where(result['c_buy_timing_score'] > 0, '右侧买入', '左侧买入')
    )
    result['c_sell_timing_tag'] = np.where(
        result['c_sell_timing_score'].isna(), None,
        np.where(result['c_sell_timing_score'] > 0, '左侧卖出', '右侧卖出')
    )


def _assign_crowd_tag(result: pd.DataFrame, fund_types: pd.DataFrame) -> None:
    """全市场+同公司排名等权复合，按基金类型70%/30%阈值打抱团标签（原地修改）"""
    df = _merge_types(result, fund_types)

    mkt_rank = df.groupby('c_type1_code')['c_crowd_score'].rank(pct=True, na_option='keep')
    int_rank = df.groupby('c_type1_code')['c_crowd_internal_score'].rank(pct=True, na_option='keep')
    composite = (mkt_rank + int_rank) / 2

    tags = np.where(composite >= 0.7, '高抱团',
           np.where(composite <= 0.3, '低抱团', '中抱团'))
    result['c_crowd_tag'] = np.where(composite.isna(), None, tags)


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date 为报告期如 '2025-12-31'"""
    report_date = calc_date
    logger.info(f"开始计算 {report_date} 组合特征标签")

    q_periods = generate_report_dates(report_date, 8)
    s_periods = [d for d in q_periods if d[5:] in ('06-30', '12-31')]
    # 持股扩新需要 T + T-1~T-3 期半年报，共7期
    s_periods_ext = [d for d in generate_report_dates(report_date, 14) if d[5:] in ('06-30', '12-31')]

    with DorisConnector(ENV) as doris:
        t_run = time.perf_counter()

        with _step("查询: fund_types"):
            fund_types = _get_fund_types(doris, report_date)
            fund_codes = fund_types['c_fd_code'].tolist()
        logger.info(f"基金 {len(fund_codes)} 只，季度窗口: {q_periods[0]}~{q_periods[-1]}，半年报窗口: {s_periods[0]}~{s_periods[-1]}")

        with _step("查询: ind_weight"):
            ind_df = _query_ind_weight(doris, fund_codes, s_periods)

        with _step("查询: heavy_stk"):
            heavy_df = _query_heavy_stk(doris, fund_codes, q_periods)

        with _step("查询: full_stk"):
            full_df = _query_full_stk(doris, fund_codes, s_periods_ext)

        with _step(f"查询: benchmark({len(s_periods)}期)"):
            benchmark = _query_benchmark(doris, s_periods)

        with _step("计算: 集中度指标"):
            sector_hhi = _calc_sector_hhi(ind_df)
            ind_conc = _calc_ind_concentration(ind_df)
            top10 = _calc_top10_ratio(heavy_df)

        with _step("计算: 主动偏离"):
            active = _calc_active_deviation(ind_df, benchmark)

        with _step("计算: 持股扩新"):
            new_stk = _calc_new_stk_ratio(full_df, report_date)

        with _step("计算: 重仓交易特征"):
            heavy = _calc_heavy_trade(heavy_df)

        dfs = [sector_hhi, ind_conc, top10, active, new_stk, heavy]
        result = reduce(lambda l, r: l.merge(r, on='c_fd_code', how='outer'), dfs)

        _assign_concentration_tags(result, fund_types)
        _assign_active_tags(result, fund_types)
        _assign_trade_tags(result, fund_types)

        with _step("查询+计算: 换手率"):
            turnover = _calc_turnover(doris, fund_codes, report_date)

        with _step("查询+计算: 抱团度"):
            crowd = _calc_crowd_scores(doris, fund_codes, report_date)

        with _step("查询+计算: 买卖时机"):
            timing = _calc_timing_scores(doris, fund_codes, report_date)

        result = result.merge(turnover, on='c_fd_code', how='left')
        result = result.merge(crowd, on='c_fd_code', how='left')
        result = result.merge(timing, on='c_fd_code', how='left')

        _assign_turnover_tag(result, fund_types)
        _assign_crowd_tag(result, fund_types)
        _assign_timing_tags(result)

        result['c_report_date'] = pd.to_datetime(report_date)

        with _step("写入: Stream Load"):
            doris.insert('tb_fd_tag_stk_portfolio', result[OUTPUT_COLS])

    logger.info(f"写入完成: {len(result)} 条，总耗时 {time.perf_counter() - t_run:.2f}s")


if __name__ == '__main__':
    import sys as _sys

    if len(_sys.argv) > 1:
        # DS 调度入口：传入 '20250630' 格式
        raw = _sys.argv[1]
        run(f'{raw[:4]}-{raw[4:6]}-{raw[6:]}')
    else:
        # 历史补数：从2016-03-31起，季度频率
        for dt in generate_report_dates('2025-12-31', 40):
            run(dt)

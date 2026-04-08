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
import yaml
import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates, get_last_quarter_end

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ENV = 'dev'

# 从 YAML 加载行业→板块映射
_YAML_PATH = Path(__file__).resolve().parent / 'sector_mapping.yaml'
with open(_YAML_PATH, 'r', encoding='utf-8') as f:
    _config = yaml.safe_load(f)
SECTOR_MAP = _config['mapping']
SECTOR_CN = _config['sectors']
SECTORS = list(SECTOR_CN.keys())

OUTPUT_COLS = [
    'c_report_date', 'c_fd_code',
    'c_hk_ratio_avg', 'c_hk_ratio_latest', 'c_region_tag',
    'c_sector_cycle', 'c_sector_mfg', 'c_sector_tech',
    'c_sector_consumer', 'c_sector_pharma', 'c_sector_fin',
    'c_sector_chg', 'c_sector_tag', 'c_sector_pref',
]


# ==================== 数据查询 ====================

def _get_fund_codes(doris: DorisConnector, report_date: str) -> list[str]:
    """取前四类基金主代码（排除A/C/B/I份额重复）"""
    sql = """
    SELECT DISTINCT c.c_fd_code FROM tytdata.tb_fd_category c
    JOIN tytdata.tb_fd_basic_info b ON c.c_fd_code = b.c_fd_code
    WHERE c.c_type1_code IN ('001','002','003','004')
      AND c.c_report_date = :report_date
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    """
    df = doris.query(sql, report_date=report_date)
    return df['c_fd_code'].tolist()


def _query_hk_data(doris: DorisConnector, fund_codes: list[str],
                   periods: list[str]) -> pd.DataFrame:
    """查询各季度港股占股票比
    去重: ORDER BY c_style → 同一报告期优先取更完整的报表类型"""
    sql = """
    WITH ranked AS (
        SELECT c_fd_code, c_report_date,
               c_stk_hk_connect_ratio, c_stk_total_ratio,
               ROW_NUMBER() OVER (
                   PARTITION BY c_fd_code, c_report_date ORDER BY c_style
               ) AS rn
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_fd_code IN (:code_list)
          AND c_report_date = :report_date
    )
    SELECT c_fd_code, c_report_date,
           IFNULL(c_stk_total_ratio, 0) AS c_stk_total_ratio,
           CASE WHEN IFNULL(c_stk_total_ratio, 0) > 0
                THEN IFNULL(c_stk_hk_connect_ratio, 0) / c_stk_total_ratio * 100
                ELSE 0 END AS hk_ratio
    FROM ranked WHERE rn = 1
    """
    dfs = []
    for report_date in periods:
        df = doris.query_batch(sql, code_list=fund_codes,
                               report_date=report_date)
        dfs.append(df)
    result_df: pd.DataFrame = pd.concat(dfs, ignore_index=True)
    result_df['c_report_date'] = pd.to_datetime(result_df['c_report_date'])
    return result_df


def _query_sector_data(doris: DorisConnector, fund_codes: list[str],
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


# ==================== 特征计算 ====================

def _calc_region(hk_df: pd.DataFrame) -> pd.DataFrame:
    """计算区域特征：均值、最新值、标签"""
    df = hk_df.sort_values(['c_fd_code', 'c_report_date'])
    avg = df.groupby('c_fd_code')['hk_ratio'].mean().round(4).rename('c_hk_ratio_avg')
    # 显式取最新报告期的值
    idx_latest = df.groupby('c_fd_code')['c_report_date'].idxmax()
    latest = df.loc[idx_latest].set_index('c_fd_code')['hk_ratio'].round(4) \
               .rename('c_hk_ratio_latest')
    agg = pd.concat([avg, latest], axis=1).reset_index()
    agg['c_region_tag'] = pd.cut(
        agg['c_hk_ratio_avg'],
        bins=[-np.inf, 20.0, 60.0, np.inf],
        labels=['A股', '均衡', '港股']
    ).astype(str)
    return agg


def _pivot_sector(ind_df: pd.DataFrame) -> pd.DataFrame:
    """行业权重聚合到六大板块宽表（基金×期）"""
    df = ind_df.copy()
    df['sector'] = df['c_ind_code'].map(SECTOR_MAP)
    df = df.dropna(subset=['sector'])
    pivot = (df.groupby(['c_fd_code', 'c_report_date', 'sector'])['c_weight']
               .sum().unstack('sector', fill_value=0).reset_index())
    for s in SECTORS:
        if s not in pivot.columns:
            pivot[s] = 0.0
    return pivot


def _calc_sector_chg(df: pd.DataFrame) -> pd.Series:
    """板块权重变动指标：各板块绝对变化均值按板块权重均值加权
    仅1期数据的基金 diff 全NaN → chg=0 → 默认均衡型"""
    df = df.sort_values(['c_fd_code', 'c_report_date'])

    def _weighted_chg(g: pd.DataFrame) -> float:
        avg_w = g[SECTORS].mean()
        mean_abs_chg = g[SECTORS].diff().abs().mean().fillna(0)
        denom = avg_w.sum()
        return float((avg_w * mean_abs_chg).sum() / denom) if denom > 0 else 0.0

    return df.groupby('c_fd_code').apply(_weighted_chg, include_groups=False).round(4)


def _assign_tag(row: pd.Series) -> pd.Series:
    """打板块标签"""
    max_w = row[[f'c_sector_{s}' for s in SECTORS]].max()
    chg = row['c_sector_chg']
    if chg >= 20 and max_w * (1 - chg / 100) <= 50:
        return pd.Series({'c_sector_tag': '轮动型', 'c_sector_pref': ''})
    if max_w > 50:
        sector_cols = {f'c_sector_{s}': s for s in SECTORS}
        best_col = row[[f'c_sector_{s}' for s in SECTORS]].idxmax()
        pref = SECTOR_CN[sector_cols[best_col]]
        return pd.Series({'c_sector_tag': '赛道型', 'c_sector_pref': pref})
    return pd.Series({'c_sector_tag': '均衡型', 'c_sector_pref': ''})


def _calc_sector_features(sector_wide: pd.DataFrame) -> pd.DataFrame:
    """计算板块均值、变动指标、标签"""
    avg_w = (sector_wide.groupby('c_fd_code')[SECTORS]
               .mean().round(4).reset_index()
               .rename(columns={s: f'c_sector_{s}' for s in SECTORS}))
    chg = _calc_sector_chg(sector_wide).rename('c_sector_chg')
    result = avg_w.join(chg, on='c_fd_code')
    tags = result.apply(_assign_tag, axis=1, result_type='expand')
    return pd.concat([result, tags], axis=1)


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date为报告期如'2024-06-30'
    四季报在年报未披露时板块特征复用上期，年报披露后重跑即覆盖(UNIQUE KEY)"""
    # report_date = get_last_quarter_end(calc_date)
    report_date = calc_date
    logger.info(f"开始计算 {report_date} 区域/板块特征标签")

    # 固定报告期列表，不依赖数据库中实际存在的期数
    q_periods = generate_report_dates(report_date, 8)
    s_periods = [d for d in generate_report_dates(report_date, 8) if d[5:] in ('06-30', '12-31')]

    with DorisConnector(ENV) as doris:
        fund_codes = _get_fund_codes(doris, report_date)
        logger.info(f"基金 {len(fund_codes)} 只")
        logger.info(f"季度窗口: {q_periods[0]}~{q_periods[-1]}  "
                    f"半年报窗口: {s_periods[0]}~{s_periods[-1]}")

        hk_df = _query_hk_data(doris, fund_codes, q_periods)
        # 过滤近8期股票持仓全为0的基金（债基/无股票持仓）
        stk_codes = set(hk_df.loc[hk_df['c_stk_total_ratio'] > 0, 'c_fd_code'])
        hk_df = hk_df[hk_df['c_fd_code'].isin(stk_codes)]
        logger.info(f"过滤后有股票持仓基金 {len(stk_codes)} 只（排除 {len(fund_codes)-len(stk_codes)} 只）")
        ind_df = _query_sector_data(doris, list(stk_codes), s_periods)

        region_df = _calc_region(hk_df)
        sector_df = _calc_sector_features(_pivot_sector(ind_df))

        # outer: 季报覆盖范围 > 半年报，部分基金可能只有区域或板块特征
        result = region_df.merge(sector_df, on='c_fd_code', how='outer')
        result['c_report_date'] = pd.to_datetime(report_date)
        result = result[OUTPUT_COLS]

        doris.insert('tb_fd_tag_stk_region_sector', result)

    logger.info(f"写入完成: {len(result)} 条")


if __name__ == '__main__':
    from utils.common import generate_report_dates

    main_trade_dates = generate_report_dates('2025-12-31', 41)
    for dt in main_trade_dates:
        run(dt)
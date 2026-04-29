"""公募基金 IPO 打新收益归因 ETL

用法:
    python insert.py --init                # 全量初始化(2019+)
    python insert.py --season 2026-Q1      # 增量跑批
"""
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

import re
import argparse
import numpy as np
import pandas as pd
from functools import partial

from utils.db_connector import OracleConnector, DorisConnector
from utils.common import get_last_quarter_end
from utils.log import setup_logger, step

from _logic import (
    LOCK_PAT,
    BOARD_PREFIXES,
    REGIME_START,
    parse_lock_ratio,
    determine_board,
    determine_regime,
)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"
logger = setup_logger(__name__)
_step = partial(step, logger)

# ==================== Constants ====================

OUTPUT_COLS = [
    'c_fd_code', 'c_init_code', 'c_stk_code', 'c_stk_inner_code',
    'c_finance_code', 'c_board', 'c_regime', 'c_list_date', 'c_sell_date',
    'c_issue_price', 'c_sell_vwap', 'c_confirmed_return',
    'c_alloc_qty_total', 'c_lock_ratio', 'c_alloc_qty_unlocked',
    'c_pnl_unlocked', 'c_net_asset_estimate', 'c_net_asset_report_date',
    'c_size_method',
]

DATA_START = '2019-01-01'

# ==================== Query Functions ====================


def _query_ipo_placement(
    oracle: OracleConnector,
    start_date: str,
    end_date: str = '2099-12-31',
) -> pd.DataFrame:
    """从 Oracle 拉取 IPO 配售明细（按 NOTICEDATE 过滤）

    Returns:
        DataFrame with columns:
        c_finance_code, c_issue_price, c_stk_inner_code,
        c_fd_code, c_alloc_qty_total, lock_text
    """
    sql = """
    SELECT
        i.FINANCECODE            AS c_finance_code,
        i.ISSUEPRICE             AS c_issue_price,
        i.SECURITY_INNER_CODE    AS c_stk_inner_code,
        p.PLACING_OBJECT_CODE    AS c_fd_code,
        SUM(p.SHAREPLACE)        AS c_alloc_qty_total,
        MAX(p.LOCKPERIOD)        AS lock_text
    FROM TYTFUND.CPI_ISSUEBASICINFO i
    JOIN TYTFUND.CPI_PLACERESULT p
      ON p.FINANCECODE = i.FINANCECODE
    WHERE i.SECURITYTYPECODE = '058001001'
      AND i.FINATYPE = '001'
      AND p.PLACEOBJECTTYPE = '网下机构投资者'
      AND p.PLACING_OBJECT_CODE IS NOT NULL
      AND i.NOTICEDATE >= :start_date
      AND i.NOTICEDATE <= :end_date
    GROUP BY i.FINANCECODE, i.ISSUEPRICE, i.SECURITY_INNER_CODE,
             p.PLACING_OBJECT_CODE
    """
    return oracle.query(sql, start_date=start_date, end_date=end_date)


def _query_stk_info(
    doris: DorisConnector, inner_codes: list[int],
) -> pd.DataFrame:
    """通过内码关联获取股票代码和上市日"""
    sql = """
    SELECT c_inner_code AS c_stk_inner_code,
           c_stk_code,
           c_list_date
    FROM tytdata.tb_stk_basic_info
    WHERE c_inner_code IN (:code_list)
    """
    return doris.query_batch(sql, code_list=inner_codes)


def _query_init_code_map(
    doris: DorisConnector, fd_codes: list[str],
) -> pd.DataFrame:
    """基金子份额 → 主代码映射（同时过滤掉非公募基金）"""
    sql = """
    SELECT c_fd_code, c_init_code
    FROM tytdata.tb_fd_basic_info
    WHERE c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, code_list=fd_codes)


# ==================== Processing Functions ====================


def _enrich_and_apply_rules(
    raw: pd.DataFrame,
    doris: DorisConnector,
) -> pd.DataFrame:
    """关联股票信息 → 过滤公募 → 判定板块/制度/锁定比例"""
    inner_codes = raw['c_stk_inner_code'].unique().tolist()

    with _step("Doris: 关联股票信息"):
        stk_info = _query_stk_info(doris, inner_codes)
    df = raw.merge(stk_info, on='c_stk_inner_code', how='inner')

    # 过滤: 只保留 2019+ 上市的 IPO
    df['c_list_date'] = pd.to_datetime(df['c_list_date'])
    df = df[df['c_list_date'] >= DATA_START].copy()
    if df.empty:
        return df

    with _step("Doris: 匹配主代码(过滤非公募)"):
        init_map = _query_init_code_map(doris, df['c_fd_code'].unique().tolist())
    df = df.merge(init_map, on='c_fd_code', how='inner')
    logger.info(f"  公募基金命中 {len(df)} 行 / 原始 {len(raw)} 行")

    with _step("判定板块/制度/锁定比例"):
        df['c_stk_code'] = df['c_stk_code'].astype(str)
        df['c_board'] = df['c_stk_code'].apply(determine_board)
        list_date_str = df['c_list_date'].dt.strftime('%Y-%m-%d')
        df['c_regime'] = [
            determine_regime(b, d)
            for b, d in zip(df['c_board'], list_date_str)
        ]
        df['c_lock_ratio'] = df['lock_text'].apply(parse_lock_ratio)
        df['c_alloc_qty_unlocked'] = (
            df['c_alloc_qty_total'] * (1 - df['c_lock_ratio'])
        )

    df.drop(columns=['lock_text'], inplace=True)
    return df


def _assign_sell_dates(
    df: pd.DataFrame, doris: DorisConnector,
) -> pd.DataFrame:
    """注册制 → 卖出日=上市日；核准制 → 卖出日=首次开板日"""
    reg_mask = df['c_regime'] == 'registration'
    df.loc[reg_mask, 'c_sell_date'] = df.loc[reg_mask, 'c_list_date']

    appr_mask = df['c_regime'] == 'approval'
    if not appr_mask.any():
        return df

    appr_codes = df.loc[appr_mask, 'c_stk_code'].unique().tolist()
    logger.info(f"  核准制 IPO {len(appr_codes)} 只，查询首次开板日")

    first_open = doris.query_batch(
        """
        SELECT c_stk_code,
               MIN(c_trade_date) AS first_open_date
        FROM tytdata.tb_stk_quote_daily
        WHERE c_stk_code IN (:code_list)
          AND c_is_limit_up = '否'
        GROUP BY c_stk_code
        """,
        code_list=appr_codes,
    )
    open_map = dict(zip(first_open['c_stk_code'], first_open['first_open_date']))
    df.loc[appr_mask, 'c_sell_date'] = (
        df.loc[appr_mask, 'c_stk_code'].map(open_map)
    )

    n_missing = df['c_sell_date'].isna().sum()
    if n_missing:
        logger.warning(f"  {n_missing} 行卖出日未确定(尚未开板)，将跳过")

    df['c_sell_date'] = pd.to_datetime(df['c_sell_date'])
    return df


def _query_sell_vwap(
    df: pd.DataFrame, doris: DorisConnector,
) -> pd.DataFrame:
    """按卖出日分组批量查询 VWAP = c_amount / c_volume"""
    results = []
    sell_groups = df.groupby('c_sell_date')['c_stk_code'].apply(
        lambda s: s.unique().tolist()
    )
    for sell_date, stk_codes in sell_groups.items():
        vwap = doris.query_batch(
            """
            SELECT c_stk_code,
                   c_amount / c_volume AS c_sell_vwap
            FROM tytdata.tb_stk_quote_daily
            WHERE c_stk_code IN (:code_list)
              AND c_trade_date = :trade_date
              AND c_volume > 0
            """,
            code_list=stk_codes,
            trade_date=str(sell_date)[:10],
        )
        results.append(vwap)

    if not results:
        df['c_sell_vwap'] = np.nan
        return df

    vwap_df = pd.concat(results, ignore_index=True)
    df = df.merge(vwap_df, on='c_stk_code', how='left')
    return df


def _calc_pnl(df: pd.DataFrame) -> pd.DataFrame:
    """计算确认涨幅和无锁定部分浮盈"""
    df['c_confirmed_return'] = (
        (df['c_sell_vwap'] - df['c_issue_price']) / df['c_issue_price']
    )
    df['c_pnl_unlocked'] = (
        df['c_alloc_qty_unlocked'] * (df['c_sell_vwap'] - df['c_issue_price'])
    )
    return df


def _query_net_asset_data(
    doris: DorisConnector, init_codes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """查询主代码下所有子份额及其季报净资产

    Returns:
        sub_shares: DataFrame[c_fd_code, c_init_code]
        net_assets: DataFrame[c_fd_code, c_report_date, c_net_asset]（按日期升序）
    """
    sub_shares = doris.query_batch(
        """
        SELECT c_fd_code, c_init_code
        FROM tytdata.tb_fd_basic_info
        WHERE c_init_code IN (:code_list)
        """,
        code_list=init_codes,
    )

    all_fd_codes = sub_shares['c_fd_code'].unique().tolist()
    net_assets = doris.query_batch(
        """
        SELECT c_fd_code,
               c_report_date,
               MAX(c_fund_nav_total) AS c_net_asset
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_fd_code IN (:code_list)
        GROUP BY c_fd_code, c_report_date
        """,
        code_list=all_fd_codes,
    )
    net_assets['c_report_date'] = pd.to_datetime(net_assets['c_report_date'])
    net_assets = net_assets.sort_values(['c_fd_code', 'c_report_date'])
    return sub_shares, net_assets


def _calc_net_asset_estimate(
    df: pd.DataFrame, doris: DorisConnector,
) -> pd.DataFrame:
    """计算规模分母（主代码 × 卖出日层面，子份额加总）

    使用 pd.merge_asof 向量化匹配前后两期季报净资产。
    """
    init_codes = df['c_init_code'].unique().tolist()
    sub_shares, net_assets = _query_net_asset_data(doris, init_codes)

    # (init_code, sell_date) 去重 → 展开到子份额粒度
    pairs = df[['c_init_code', 'c_sell_date']].drop_duplicates()
    grid = pairs.merge(sub_shares, on='c_init_code')
    grid['c_sell_date'] = pd.to_datetime(grid['c_sell_date'])
    grid = grid.sort_values(['c_fd_code', 'c_sell_date']).reset_index(drop=True)

    # merge_asof: 前向匹配 prev_q
    na_prev = net_assets.copy()
    na_prev['prev_report_date'] = na_prev['c_report_date']
    na_prev = na_prev.rename(
        columns={'c_report_date': 'c_sell_date', 'c_net_asset': 'prev_nav'}
    )
    na_prev = na_prev.sort_values(['c_fd_code', 'c_sell_date'])

    prev = pd.merge_asof(
        grid, na_prev[['c_fd_code', 'c_sell_date', 'prev_nav', 'prev_report_date']],
        on='c_sell_date', by='c_fd_code', direction='backward',
    )

    # merge_asof: 后向匹配 next_q
    na_next = net_assets.rename(
        columns={'c_report_date': 'c_sell_date', 'c_net_asset': 'next_nav'}
    )
    na_next = na_next.sort_values(['c_fd_code', 'c_sell_date'])

    next_df = pd.merge_asof(
        grid, na_next[['c_fd_code', 'c_sell_date', 'next_nav']],
        on='c_sell_date', by='c_fd_code', direction='forward',
    )
    prev['next_nav'] = next_df['next_nav'].values

    # 计算单个子份额估算值
    has_both = prev['prev_nav'].notna() & prev['next_nav'].notna()
    prev['fd_estimate'] = np.where(
        has_both,
        (prev['prev_nav'] + prev['next_nav']) / 2,
        prev['prev_nav'],
    )
    # 跳过无 prev_q 的子份额（基金成立未满一季度）
    prev = prev.dropna(subset=['prev_nav'])

    # 聚合到 (init_code, sell_date) 层面
    est = prev.groupby(['c_init_code', 'c_sell_date']).agg(
        c_net_asset_estimate=('fd_estimate', 'sum'),
        c_net_asset_report_date=('prev_report_date', 'first'),
        c_size_method=('next_nav', lambda x: (
            'quarterly_avg' if x.notna().all() else 'quarterly_ffill'
        )),
    ).reset_index()

    df['c_sell_date'] = pd.to_datetime(df['c_sell_date'])
    df = df.merge(est, on=['c_init_code', 'c_sell_date'], how='left')
    return df


# ==================== Orchestration ====================


def _process_placements(
    oracle: OracleConnector,
    doris: DorisConnector,
    start_date: str,
    end_date: str = '2099-12-31',
) -> pd.DataFrame:
    """核心流水线：拉取 → 清洗 → 计算 → 返回 DataFrame"""
    with _step("Oracle: 拉取 IPO 配售明细"):
        raw = _query_ipo_placement(oracle, start_date, end_date)
    logger.info(f"  Oracle 返回 {len(raw)} 行")
    if raw.empty:
        return raw

    df = _enrich_and_apply_rules(raw, doris)
    if df.empty:
        logger.warning("  enrichment 后无数据")
        return df

    with _step("确定卖出日"):
        df = _assign_sell_dates(df, doris)
    df = df.dropna(subset=['c_sell_date'])
    if df.empty:
        logger.warning("  无有效卖出日")
        return df

    with _step("查询卖出日 VWAP"):
        df = _query_sell_vwap(df, doris)
    n_no_vwap = df['c_sell_vwap'].isna().sum()
    if n_no_vwap:
        logger.warning(f"  {n_no_vwap} 行 VWAP 缺失(停牌/退市)，跳过")
    df = df.dropna(subset=['c_sell_vwap'])

    with _step("计算浮盈"):
        df = _calc_pnl(df)

    with _step("计算规模分母"):
        df = _calc_net_asset_estimate(df, doris)

    logger.info(f"  最终 {len(df)} 行待写入")
    return df


def run_init():
    """全量初始化：拉取 2019+ 全部 IPO 配售数据"""
    logger.info("========== 全量初始化模式 ==========")
    with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
        # NOTICEDATE 提前半年以覆盖 2019-01-01 上市的 IPO
        df = _process_placements(oracle, doris, start_date='2018-06-01')
        if df.empty:
            logger.warning("无数据写入")
            return
        logger.info(f"写入 {len(df)} 行")
        doris.insert('tb_fd_ipo_return', df[OUTPUT_COLS])
    logger.info("========== 全量初始化完成 ==========")


def _parse_season(season: str) -> tuple[str, str]:
    """解析 --season 参数，返回 (prev_quarter_end, quarter_end)"""
    m = re.match(r'(\d{4})-Q([1-4])', season)
    if not m:
        raise ValueError(f"无效格式: {season}，应为 YYYY-Q1/Q2/Q3/Q4")
    year, q = int(m.group(1)), int(m.group(2))
    ends = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
    quarter_end = f"{year}-{ends[q]}"
    prev_ends = {
        1: f"{year - 1}-12-31", 2: f"{year}-03-31",
        3: f"{year}-06-30", 4: f"{year}-09-30",
    }
    return prev_ends[q], quarter_end


def run_season(season: str):
    """增量跑批：处理指定季度新上市的 IPO"""
    prev_end, quarter_end = _parse_season(season)
    logger.info(f"========== 增量模式: {season} ({prev_end} ~ {quarter_end}] ==========")

    # Oracle NOTICEDATE 窗口：提前 3 个月以覆盖本季度上市的 IPO
    notice_start = str(pd.Timestamp(prev_end) - pd.DateOffset(months=3))[:10]

    with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
        df = _process_placements(oracle, doris, notice_start, quarter_end)
        if df.empty:
            logger.warning("无数据")
            return

        # 过滤：仅保留 c_list_date 在本季度窗口内的 IPO
        df = df[
            (df['c_list_date'] > prev_end) & (df['c_list_date'] <= quarter_end)
        ]
        if df.empty:
            logger.info("本季度无新 IPO")
            return

        logger.info(f"写入 {len(df)} 行 (UNIQUE KEY 覆盖)")
        doris.insert('tb_fd_ipo_return', df[OUTPUT_COLS])
    logger.info(f"========== 增量完成: {season} ==========")


# ==================== CLI ====================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='公募打新收益归因 ETL')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--init', action='store_true',
                       help='全量初始化(2019+)')
    group.add_argument('--season', type=str,
                       help='增量跑批, 格式: YYYY-Q1/Q2/Q3/Q4')
    args = parser.parse_args()

    if args.init:
        run_init()
    else:
        run_season(args.season)

"""
主动管理型基金筛选 — 第十条核心筛选逻辑

筛选步骤：
  Step1  基础筛选
         (1) 基金公司主动权益规模 ≥50亿 且 行业排名前50%
             主动权益定义：近4个季报股票仓位均值 ≥60% 的三类基金
         (2) 单只基金规模 ≥2亿
         (3) 基金经理公开历史业绩累计 ≥1年（不局限于当前产品）
         (4) 剔除非开放申购基金
  Step2  赛道分类
         直接取 tytfund.tb_fd_equity_topic 中的主题标签
         未收录基金归入"全市场"
  Step3  打分（各指标同赛道百分位排名加权）
         长期业绩(65%)：近3年年化超额（不足3年取成立以来年化）
         短期业绩(15%)：近1年区间超额
         最大回撤(10%)：近1年，越小越好
         夏普比率(10%)：近1年
  Step4  最终入池
         全市场类前50% + 各赛道前50%

输出：data/active_fund_pool.xlsx（5个 Sheet）
  基金数量统计 / 基金公司规模 / 全量三类基金 / 基础筛选后 / 初选池-全市场50%
"""
from pathlib import Path

import pandas as pd
from utils.db_connector import DorisConnector, OracleConnector
from utils.log import setup_logger

logger = setup_logger(__name__)

ENV = 'dev'

# ── 参数（按需修改）────────────────────────────────────────────────────────────
SCALE_REPORT_DATE = '2025-12-31'          # 规模基准报告期（2025年报）
PERF_CALC_DATE    = '2026-04-08'          # 业绩计算截止日（最新交易日）
MIN_COMPANY_SCALE = 50.0                  # 基金公司主动权益规模下限（亿元）
MIN_FUND_SCALE    = 2.0                   # 单只基金规模下限（亿元）
MIN_MGR_DAYS      = 365                   # 经理公开业绩最短天数

# 纳入筛选的内部分类代码：普通股票型 + 偏股混合型 + 灵活配置型
ACTIVE_TYPES = ('001001', '002001', '002004')

# 打分权重
SCORE_WEIGHTS = {
    'long_excess':  0.65,
    'short_excess': 0.15,
    'neg_mdd':      0.10,
    'sharpe':       0.10,
}


def _equity_ratio_periods(scale_date: str) -> list:
    """返回 scale_date 所在年度四个季报期（用于股票仓位均值 ≥60% 过滤）。"""
    year = scale_date[:4]
    return [f'{year}-03-31', f'{year}-06-30', f'{year}-09-30', f'{year}-12-31']


# ── 数据拉取 ──────────────────────────────────────────────────────────────────

def _fetch_universe(doris: DorisConnector) -> pd.DataFrame:
    """全量三类基金宇宙：主代码、未清盘、已成立。不做申购状态过滤。"""
    sql = """
    SELECT c_fd_code, c_short_name, c_company_code, c_company_name,
           c_manager_code, c_manager_name, c_purchase_status, c_estabdate,
           c_class2_code, c_class2_name
    FROM tb_fd_basic_info
    WHERE c_class2_code IN ('001001', '002001', '002004')
      AND c_terminate_date IS NULL
      AND (c_init_code = c_fd_code OR c_init_code IS NULL)
      AND c_estabdate < '2026-03-31'
    """
    return doris.query(sql)


def _fetch_fund_scale(doris: DorisConnector, fd_codes: list) -> pd.DataFrame:
    """单只基金规模（亿元）：取年报 c_fund_nav_total，元→亿。"""
    sql = """
    SELECT c_fd_code,
           c_fund_nav_total / 100000000 AS c_scale_bn
    FROM tb_fd_asset_allocation
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style = '04'
    """
    return doris.query_batch(sql, fd_codes, report_date=SCALE_REPORT_DATE)


def _fetch_company_scale(doris: DorisConnector) -> pd.DataFrame:
    """
    按公司汇总主动权益规模（亿元），计算全市场百分位排名。
    主动权益定义：三类基金 + 近4个季报（同年Q1-Q4）股票仓位均值 ≥60%。
    """
    periods = _equity_ratio_periods(SCALE_REPORT_DATE)
    sql = """
    SELECT b.c_company_code, b.c_company_name,
           SUM(a.c_fund_nav_total) / 100000000 AS c_co_scale_bn
    FROM tb_fd_asset_allocation a
    JOIN tb_fd_basic_info b ON b.c_fd_code = a.c_fd_code
    JOIN (
        SELECT c_fd_code
        FROM tb_fd_asset_allocation
        WHERE c_report_date IN (:p1, :p2, :p3, :p4)
          AND c_style IN ('01', '03', '05', '06')
        GROUP BY c_fd_code
        HAVING AVG(c_stk_total_ratio) >= 60
    ) eq ON eq.c_fd_code = a.c_fd_code
    WHERE a.c_report_date = :report_date
      AND a.c_style = '04'
      AND b.c_terminate_date IS NULL
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND b.c_class2_code IN ('001001', '002001', '002004')
    GROUP BY b.c_company_code, b.c_company_name
    """
    df = doris.query(
        sql,
        p1=periods[0], p2=periods[1], p3=periods[2], p4=periods[3],
        report_date=SCALE_REPORT_DATE,
    )
    df['c_co_scale_bn'] = pd.to_numeric(df['c_co_scale_bn'], errors='coerce')
    df['c_co_rank_pct'] = df['c_co_scale_bn'].rank(pct=True, ascending=True)
    return df


def _fetch_manager_tenure(doris: DorisConnector, fd_codes: list) -> pd.DataFrame:
    """
    返回两个日期字段：
      c_mgr_earliest_start   经理跨产品最早任职日（判断公开业绩年限）
      c_mgr_curr_fund_start  上任本基金日期（展示任职年限）
    """
    sql = """
    SELECT m.c_fd_code,
           MIN(hist.c_earliest_start) AS c_mgr_earliest_start,
           MIN(m.c_start_date)        AS c_mgr_curr_fund_start
    FROM tb_fd_manager m
    JOIN (
        SELECT c_person_code, MIN(c_start_date) AS c_earliest_start
        FROM tb_fd_manager
        WHERE c_post = '基金经理'
        GROUP BY c_person_code
    ) hist ON m.c_person_code = hist.c_person_code
    WHERE m.c_post = '基金经理'
      AND m.c_is_current = -1
      AND m.c_fd_code IN (:code_list)
    GROUP BY m.c_fd_code
    """
    return doris.query_batch(sql, fd_codes)


def _fetch_equity_topic(oracle: OracleConnector) -> pd.DataFrame:
    """从 Oracle tytfund.tb_fd_equity_topic 拉取基金赛道主题。"""
    sql = """
    SELECT c_fundcode AS c_fd_code,
           CASE WHEN c_fundcode = '005851' THEN N'均衡' ELSE c_topic END AS c_sector
    FROM tytfund.tb_fd_equity_topic
    WHERE c_enddate = TO_DATE(:report_date, 'YYYY-MM-DD')
    """
    df = oracle.query(sql, report_date=SCALE_REPORT_DATE)
    df.columns = [c.lower() for c in df.columns]
    return df


def _fetch_performance(doris: DorisConnector, fd_codes: list) -> pd.DataFrame:
    """
    拉取业绩指标（截止 PERF_CALC_DATE）：
      '05' 近3年  → c_ann_ret 用于长期指标（优先）
      '08' 成立以来 → c_ann_ret 用于长期指标（备用）
      '03' 近1年  → c_period_ret / c_mdd / c_sharpe 用于短期及波动指标
    """
    sql = """
    SELECT c_fd_code, c_period_code, c_ann_ret, c_period_ret, c_mdd, c_sharpe
    FROM tb_fd_perform_abs
    WHERE c_fd_code IN (:code_list)
      AND c_trade_date = :calc_date
      AND c_period_code IN ('03', '05', '08')
    """
    return doris.query_batch(sql, fd_codes, calc_date=PERF_CALC_DATE)


# ── 筛选与计算逻辑 ────────────────────────────────────────────────────────────

def _step1_filter(
    df_universe: pd.DataFrame,
    df_fund_scale: pd.DataFrame,
    df_company_scale: pd.DataFrame,
    df_mgr_tenure: pd.DataFrame,
) -> pd.DataFrame:
    """Step1 基础筛选：开放申购 + 基金规模 + 公司规模/排名 + 经理年限。"""
    df = df_universe.copy()

    # (4) 开放申购
    df = df[df['c_purchase_status'] == '开放申购']
    logger.info(f"  仅开放申购后：{len(df)} 只")

    # (2) 基金规模 ≥ 2亿
    df_fund_scale = df_fund_scale.copy()
    df_fund_scale['c_scale_bn'] = pd.to_numeric(df_fund_scale['c_scale_bn'], errors='coerce')
    df = df.merge(df_fund_scale[['c_fd_code', 'c_scale_bn']], on='c_fd_code', how='left')
    df = df[df['c_scale_bn'] >= MIN_FUND_SCALE]
    logger.info(f"  单只规模 ≥{MIN_FUND_SCALE}亿 后：{len(df)} 只")

    # (1) 公司规模 ≥ 50亿 且 排名前50%
    co_pass = df_company_scale[
        (df_company_scale['c_co_scale_bn'] >= MIN_COMPANY_SCALE) &
        (df_company_scale['c_co_rank_pct'] >= 0.5)
    ][['c_company_code', 'c_co_scale_bn', 'c_co_rank_pct']]
    df = df.merge(co_pass, on='c_company_code', how='inner')
    logger.info(f"  公司规模/排名达标后：{len(df)} 只")

    # (3) 经理公开历史业绩 ≥ 1年（跨产品累计）
    df = df.merge(
        df_mgr_tenure[['c_fd_code', 'c_mgr_earliest_start', 'c_mgr_curr_fund_start']],
        on='c_fd_code', how='left'
    )
    today = pd.Timestamp.today().normalize()
    df['c_mgr_earliest_start']  = pd.to_datetime(df['c_mgr_earliest_start'])
    df['c_mgr_curr_fund_start'] = pd.to_datetime(df['c_mgr_curr_fund_start'])
    df = df[(today - df['c_mgr_earliest_start']).dt.days >= MIN_MGR_DAYS]
    df['c_mgr_tenure_years'] = (
        (today - df['c_mgr_curr_fund_start']).dt.days / 365
    ).round(1)
    logger.info(f"  经理公开业绩 ≥{MIN_MGR_DAYS}天 后：{len(df)} 只")

    return df.reset_index(drop=True)


def _build_perf_wide(df_perf_raw: pd.DataFrame) -> pd.DataFrame:
    """长格式业绩表 → 宽格式，构造各指标列。"""
    perf = df_perf_raw.pivot_table(
        index='c_fd_code',
        columns='c_period_code',
        values=['c_ann_ret', 'c_period_ret', 'c_mdd', 'c_sharpe'],
        aggfunc='first',
    )
    perf.columns = ['_'.join(c) for c in perf.columns]
    perf = perf.reset_index()

    for col in ['c_ann_ret_05', 'c_ann_ret_08', 'c_period_ret_03', 'c_mdd_03', 'c_sharpe_03']:
        if col not in perf.columns:
            perf[col] = None
        perf[col] = pd.to_numeric(perf[col], errors='coerce')

    perf['long_ret']  = perf['c_ann_ret_05'].fillna(perf['c_ann_ret_08'])
    perf['short_ret'] = perf['c_period_ret_03']
    perf['mdd_1y']    = perf['c_mdd_03']
    perf['sharpe_1y'] = perf['c_sharpe_03']

    return perf[['c_fd_code', 'long_ret', 'short_ret', 'mdd_1y', 'sharpe_1y']]


def _compute_scores(
    df_step1: pd.DataFrame,
    df_sector: pd.DataFrame,
    df_perf_raw: pd.DataFrame,
) -> pd.DataFrame:
    """
    Step3 打分。
    各指标在同赛道内百分位排名（0~1），加权求和得综合得分。
    超额 = 基金值 - 同组中位数；回撤取负值再排名。
    """
    perf = _build_perf_wide(df_perf_raw)

    df = df_step1[[
        'c_fd_code', 'c_short_name', 'c_company_name', 'c_class2_name',
        'c_manager_name', 'c_mgr_curr_fund_start', 'c_mgr_tenure_years',
        'c_purchase_status', 'c_scale_bn', 'c_co_scale_bn',
    ]].copy()
    df = df.merge(df_sector[['c_fd_code', 'c_sector']], on='c_fd_code', how='left')
    df['c_sector'] = df['c_sector'].fillna('全市场')
    df = df.merge(perf, on='c_fd_code', how='left')

    scored_groups = []
    for sector, grp in df.groupby('c_sector', sort=False):
        g = grp.copy()
        g['long_excess']  = g['long_ret']  - g['long_ret'].median()
        g['short_excess'] = g['short_ret'] - g['short_ret'].median()
        g['r_long']   = g['long_excess'].rank(pct=True, na_option='bottom')
        g['r_short']  = g['short_excess'].rank(pct=True, na_option='bottom')
        g['r_mdd']    = (-g['mdd_1y']).rank(pct=True, na_option='bottom')
        g['r_sharpe'] = g['sharpe_1y'].rank(pct=True, na_option='bottom')
        g['c_total_score'] = (
            SCORE_WEIGHTS['long_excess']  * g['r_long']  +
            SCORE_WEIGHTS['short_excess'] * g['r_short'] +
            SCORE_WEIGHTS['neg_mdd']      * g['r_mdd']   +
            SCORE_WEIGHTS['sharpe']       * g['r_sharpe']
        )
        scored_groups.append(g)

    result = pd.concat(scored_groups, ignore_index=True)
    logger.info(f"Step3 打分完成：{len(result)} 只基金")
    return result


def _step4_final_pool(df_score: pd.DataFrame) -> pd.DataFrame:
    """Step4：各组（全市场 + 每个赛道）取综合得分前50%入池。"""
    pool_groups = []
    for sector, grp in df_score.groupby('c_sector', sort=False):
        threshold = grp['c_total_score'].quantile(0.5)
        passed = grp[grp['c_total_score'] >= threshold].copy()
        logger.info(f"  {sector}：{len(grp)} 只 → 入池 {len(passed)} 只")
        pool_groups.append(passed)
    return pd.concat(pool_groups, ignore_index=True)


# ── 输出格式化 ────────────────────────────────────────────────────────────────

_COL_RENAME_17 = {
    'c_sector':             '赛道',
    'c_fd_code':            '基金代码',
    'c_short_name':         '基金简称',
    'c_class2_name':        '东财三级分类',
    'c_company_name':       '基金公司',
    'c_co_scale_bn':        '基金公司主动权益基金规模',
    'c_report_date':        '报告期',
    'c_manager_name':       '基金经理',
    'c_mgr_curr_fund_start':'任职日期',
    'c_mgr_tenure_years':   '任职年限',
    'c_purchase_status':    '申购状态',
    'c_scale_bn':           '基金规模',
    'c_total_score':        '总得分',
    'short_excess':         '近一年超额收益',
    'long_excess':          '近三年或任职以来超额年化收益',
    'mdd_1y':               '最大回撤',
    'sharpe_1y':            '夏普比率',
}
_COLS_17_ORDER = list(_COL_RENAME_17.keys())


def _format_17col(df: pd.DataFrame) -> pd.DataFrame:
    """选取并重命名 17 列，报告期填入常量，任职日期格式化为字符串。"""
    out = df.copy()
    out['c_report_date'] = SCALE_REPORT_DATE
    out = out.reindex(columns=_COLS_17_ORDER).rename(columns=_COL_RENAME_17)
    out['任职日期'] = pd.to_datetime(out['任职日期']).dt.strftime('%Y-%m-%d')
    return out


# ── 主函数 ────────────────────────────────────────────────────────────────────

def run():
    logger.info("=== 主动管理型基金筛选 开始 ===")

    # 第一批查询：全量基础数据
    with DorisConnector(ENV) as doris:
        df_universe = _fetch_universe(doris)
        logger.info(f"候选宇宙：{len(df_universe)} 只基金")

        df_company_scale = _fetch_company_scale(doris)
        logger.info(f"有主动权益产品的基金公司：{len(df_company_scale)} 家")

        fd_all = df_universe['c_fd_code'].tolist()
        df_fund_scale = _fetch_fund_scale(doris, fd_all)
        df_mgr_tenure = _fetch_manager_tenure(doris, fd_all)
        df_perf_all   = _fetch_performance(doris, fd_all)

    # Step2 赛道分类（Oracle）
    logger.info("Step2 赛道分类（Oracle tb_fd_equity_topic）...")
    with OracleConnector(ENV) as oracle:
        df_topic = _fetch_equity_topic(oracle)
    logger.info(f"  话题表行数：{len(df_topic)}")

    # Step1 基础筛选
    logger.info("Step1 基础筛选...")
    df_step1 = _step1_filter(df_universe, df_fund_scale, df_company_scale, df_mgr_tenure)
    fd_pass1 = df_step1['c_fd_code'].tolist()

    # Step1 通过基金的赛道映射（未收录 → 全市场）
    df_sector = (
        pd.DataFrame({'c_fd_code': fd_pass1})
        .merge(df_topic, on='c_fd_code', how='left')
    )
    df_sector['c_sector'] = df_sector['c_sector'].fillna('全市场')
    logger.info(f"  分类结果：{df_sector['c_sector'].value_counts().to_dict()}")

    # Step3 打分（仅对 Step1 通过基金计算）
    logger.info("Step3 打分...")
    df_perf_pass1 = df_perf_all[df_perf_all['c_fd_code'].isin(fd_pass1)]
    df_score = _compute_scores(df_step1, df_sector, df_perf_pass1)

    # Step4 入池
    logger.info("Step4 入池（各组前50%）...")
    df_pool = _step4_final_pool(df_score)
    logger.info(f"最终入池：{len(df_pool)} 只基金")

    # ── 准备 Sheet3 全量数据 ─────────────────────────────────────────────────
    fund_scale_num = df_fund_scale.copy()
    fund_scale_num['c_scale_bn'] = pd.to_numeric(fund_scale_num['c_scale_bn'], errors='coerce')

    perf_wide_all = _build_perf_wide(df_perf_all)

    today = pd.Timestamp.today().normalize()
    mgr_all = df_mgr_tenure.copy()
    mgr_all['c_mgr_curr_fund_start'] = pd.to_datetime(mgr_all['c_mgr_curr_fund_start'])
    mgr_all['c_mgr_tenure_years'] = (
        (today - mgr_all['c_mgr_curr_fund_start']).dt.days / 365
    ).round(1)

    df_all = (
        df_universe
        .merge(fund_scale_num[['c_fd_code', 'c_scale_bn']], on='c_fd_code', how='left')
        .merge(df_company_scale[['c_company_code', 'c_co_scale_bn']], on='c_company_code', how='left')
        .merge(
            mgr_all[['c_fd_code', 'c_mgr_curr_fund_start', 'c_mgr_tenure_years']],
            on='c_fd_code', how='left'
        )
        .merge(df_topic, on='c_fd_code', how='left')
        .merge(
            df_score[['c_fd_code', 'c_total_score', 'short_excess', 'long_excess']],
            on='c_fd_code', how='left'
        )
        .merge(perf_wide_all[['c_fd_code', 'mdd_1y', 'sharpe_1y']], on='c_fd_code', how='left')
    )
    df_all['c_sector'] = df_all['c_sector'].fillna('全市场')

    # ── 写 Excel ─────────────────────────────────────────────────────────────
    out_path = Path(__file__).parent / 'data' / 'active_fund_pool.xlsx'
    out_path.parent.mkdir(exist_ok=True)

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        # Sheet 1：基金数量统计
        (
            df_universe.groupby('c_class2_name', as_index=False)
            .size()
            .rename(columns={'c_class2_name': '内部分类', 'size': '基金数量(只)'})
            .to_excel(writer, sheet_name='基金数量统计', index=False)
        )

        # Sheet 2：基金公司规模
        (
            df_company_scale[['c_company_name', 'c_co_scale_bn']]
            .sort_values('c_co_scale_bn', ascending=False)
            .rename(columns={
                'c_company_name': '基金公司',
                'c_co_scale_bn':  '主动权益基金规模（亿元）',
            })
            .to_excel(writer, sheet_name='基金公司规模', index=False)
        )

        # Sheet 3：全量三类基金（无筛选，打分仅对 Step1 通过基金有值）
        _format_17col(df_all).sort_values(
            ['赛道', '总得分'], ascending=[True, False], na_position='last'
        ).to_excel(writer, sheet_name='全量三类基金', index=False)

        # Sheet 4：基础筛选后（Step1 通过 + 完整打分）
        _format_17col(df_score).sort_values(
            ['赛道', '总得分'], ascending=[True, False]
        ).to_excel(writer, sheet_name='基础筛选后', index=False)

        # Sheet 5：初选池-全市场50%
        _format_17col(df_pool).sort_values(
            ['赛道', '总得分'], ascending=[True, False]
        ).to_excel(writer, sheet_name='初选池-全市场50%', index=False)

    logger.info(f"已保存至 {out_path}")
    return df_pool


if __name__ == '__main__':
    run()

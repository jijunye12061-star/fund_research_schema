"""
固收加基金整体分析（2023-2025）

分析维度：
  § 1  样本分类（12 季报截面，四分类）
  § 2  业绩走势（36 月度，中位数曲线 + 累计净值 + 箱线）
  § 3  规模与机构持有（5 半年截面）
  § 4  Top 基金定量线索

输出: data/固收加整体分析.xlsx + images/*.png
"""
from pathlib import Path
import pandas as pd
from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

# ── 参数配置 ──────────────────────────────────────────────────────────────────
# 12 个季报截面
QUARTER_DATES = [
    '2023-03-31', '2023-06-30', '2023-09-30', '2023-12-31',
    '2024-03-31', '2024-06-30', '2024-09-30', '2024-12-31',
    '2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31',
]

# 5 个半年截面（规模 + 机构持有）
HALF_YEAR_DATES = [
    '2023-12-31', '2024-06-30', '2024-12-31',
    '2025-06-30', '2025-12-31',
]

# 36 个月末自然日
MONTH_ENDS = [
    '2023-01-31','2023-02-28','2023-03-31','2023-04-30','2023-05-31','2023-06-30',
    '2023-07-31','2023-08-31','2023-09-30','2023-10-31','2023-11-30','2023-12-31',
    '2024-01-31','2024-02-29','2024-03-31','2024-04-30','2024-05-31','2024-06-30',
    '2024-07-31','2024-08-31','2024-09-30','2024-10-31','2024-11-30','2024-12-31',
    '2025-01-31','2025-02-28','2025-03-31','2025-04-30','2025-05-31','2025-06-30',
    '2025-07-31','2025-08-31','2025-09-30','2025-10-31','2025-11-30','2025-12-31',
]

OUT_DIR = Path(__file__).parent / 'data'
IMG_DIR = Path(__file__).parent / 'images'
OUT_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _get_trade_date(doris, date: str) -> str:
    """自然日 → 当日或之前最近交易日"""
    df = doris.query(
        "SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = :d",
        d=date,
    )
    return str(df.iloc[0]['c_max_trade_date'])[:10] if not df.empty else date


def _get_month_end_trade_dates(doris) -> dict:
    """返回 {自然月末: 交易日} 映射，覆盖 MONTH_ENDS 全部 36 个日期"""
    result = {}
    for d in MONTH_ENDS:
        result[d] = _get_trade_date(doris, d)
    return result


def _fetch_universe(doris, report_date: str) -> pd.DataFrame:
    """
    固收加基金池（单季报截面，主代码去重）
    返回: c_fd_code, c_fd_name, c_company_name, c_manager_name,
           c_estabdate, c_type2_code, c_eq_risk_level
    """
    sql = """
    SELECT
        b.c_fd_code,
        b.c_short_name          AS c_fd_name,
        b.c_company_name,
        b.c_manager_name,
        b.c_estabdate,
        cat.c_type2_code,
        COALESCE(ta.c_eq_risk_level, '') AS c_eq_risk_level
    FROM tb_fd_basic_info b
    JOIN tb_fd_category cat
        ON cat.c_fd_code = b.c_fd_code
       AND cat.c_report_date = :report_date
    LEFT JOIN tb_fd_tag_asset_fi ta
        ON ta.c_fd_code = b.c_fd_code
       AND ta.c_report_date = :report_date
    WHERE cat.c_type1_code = '002'
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND (b.c_terminate_date IS NULL OR b.c_terminate_date > :report_date)
    """
    return doris.query(sql, report_date=report_date)


def _classify(df_univ: pd.DataFrame) -> pd.DataFrame:
    """
    四分类打标（互斥）：
      1. 转债基金  c_type2_code == '002001'
      2. 稳健      c_eq_risk_level == '稳健'
      3. 均衡      c_eq_risk_level == '均衡'
      4. 激进      c_eq_risk_level == '激进'
    未能分类者标为 '其他'（排除在分析外）
    """
    def _label(row):
        if row['c_type2_code'] == '002001':
            return '转债基金'
        level = row['c_eq_risk_level']
        if level in ('稳健', '均衡', '激进'):
            return level
        return '其他'

    df = df_univ.copy()
    df['category'] = df.apply(_label, axis=1)
    return df[df['category'] != '其他'].copy()


def _fetch_nav_monthly(doris, fd_codes: list, trade_dates: list) -> pd.DataFrame:
    """
    批量获取月末复权净值
    trade_dates: 月末交易日列表（去重后的实际交易日）
    返回: c_fd_code, c_trade_date, c_nav_adj
    """
    frames = []
    for td in trade_dates:
        sql = """
        SELECT c_fd_code, c_trade_date, c_nav_adj
        FROM tb_fd_nav_daily
        WHERE c_trade_date = :td
          AND c_fd_code IN (:code_list)
          AND c_nav_adj IS NOT NULL AND c_nav_adj > 0
        """
        df = doris.query_batch(sql, fd_codes, td=td)
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_holder_all_shares(doris, report_date: str) -> pd.DataFrame:
    """
    获取固收加相关基金全部份额的持有人结构（不做主代码去重）
    report_date: 半年度日期 06-30 或 12-31
    返回: c_fd_code, c_init_code, c_inst_share, c_retail_share,
           c_inst_ratio, c_retail_ratio
    """
    sql = """
    SELECT
        h.c_fd_code,
        b.c_init_code,
        h.c_inst_share,
        h.c_retail_share,
        h.c_inst_ratio,
        h.c_retail_ratio
    FROM tb_fd_holder_structure h
    JOIN tb_fd_basic_info b ON b.c_fd_code = h.c_fd_code
    JOIN tb_fd_category cat ON cat.c_fd_code = b.c_init_code
    WHERE h.c_report_date = :report_date
      AND cat.c_type1_code = '002'
      AND cat.c_report_date = :report_date
      AND h.c_inst_share IS NOT NULL
    """
    return doris.query(sql, report_date=report_date)


def _fetch_nav_for_holder(doris, fd_codes: list, report_date: str) -> pd.DataFrame:
    """
    获取 report_date 对应最近交易日的单位净值（c_nav，非复权）
    用于计算机构持有规模 = c_inst_share × c_nav
    """
    trade_date = _get_trade_date(doris, report_date)
    sql = """
    SELECT c_fd_code, c_nav
    FROM tb_fd_nav_daily
    WHERE c_trade_date = :td
      AND c_fd_code IN (:code_list)
      AND c_nav IS NOT NULL AND c_nav > 0
    """
    return doris.query_batch(sql, fd_codes, td=trade_date)


# ── § 1 样本分类 ──────────────────────────────────────────────────────────────

def build_classification_panel(doris) -> pd.DataFrame:
    """
    12 季报截面 × 基金分类面板
    返回: c_fd_code, c_fd_name, c_company_name, c_manager_name,
           c_type2_code, c_eq_risk_level, category, report_date
    """
    frames = []
    for rd in QUARTER_DATES:
        df_univ = _fetch_universe(doris, rd)
        df_cls = _classify(df_univ)
        df_cls['report_date'] = rd
        frames.append(df_cls)
        logger.info(f"{rd}: {df_cls['category'].value_counts().to_dict()}")
    return pd.concat(frames, ignore_index=True)


def summarize_classification(panel: pd.DataFrame) -> pd.DataFrame:
    """
    各季报截面 × 分类的基金数量
    返回: report_date × category 的 pivot（含合计列）
    """
    cnt = (panel
           .groupby(['report_date', 'category'])
           .size()
           .reset_index(name='count'))
    pivot = cnt.pivot(index='report_date', columns='category', values='count').fillna(0).astype(int)
    pivot['合计'] = pivot.sum(axis=1)
    # 安全地选列（某些分类可能在截面不存在）
    ordered = ['稳健', '均衡', '激进', '转债基金', '合计']
    available = [c for c in ordered if c in pivot.columns]
    return pivot[available]


# ── § 2 业绩走势 ───────────────────────────────────────────────────────────────

def build_monthly_returns(doris, panel: pd.DataFrame) -> pd.DataFrame:
    """
    计算每只基金每月复权收益率（月末 → 月末）
    返回: c_fd_code, month（'2023-01'）, ret（小数）
    """
    all_codes = panel['c_fd_code'].unique().tolist()

    month_trade_dates = _get_month_end_trade_dates(doris)
    trade_dates_sorted = sorted(set(month_trade_dates.values()))

    base_date = _get_trade_date(doris, '2022-12-30')
    all_trade_dates = [base_date] + trade_dates_sorted

    logger.info(f"拉取月末净值: {len(all_codes)} 只基金 × {len(all_trade_dates)} 个交易日")
    df_nav = _fetch_nav_monthly(doris, all_codes, all_trade_dates)

    if df_nav.empty:
        return pd.DataFrame()

    df_nav['c_trade_date'] = df_nav['c_trade_date'].astype(str).str[:10]
    df_nav = df_nav.sort_values(['c_fd_code', 'c_trade_date'])

    nav_matrix = df_nav.pivot(index='c_fd_code', columns='c_trade_date', values='c_nav_adj')

    dates = sorted(nav_matrix.columns)
    ret_frames = []
    for i in range(1, len(dates)):
        prev_d, curr_d = dates[i - 1], dates[i]
        month_label = curr_d[:7]
        ret = (nav_matrix[curr_d] / nav_matrix[prev_d] - 1).dropna()
        ret_df = ret.reset_index()
        ret_df.columns = ['c_fd_code', 'ret']
        ret_df['month'] = month_label
        ret_frames.append(ret_df)

    return pd.concat(ret_frames, ignore_index=True)


def calc_category_monthly_median(
    monthly_ret: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    动态样本：每月取当月所属季报期的分类标签
    返回: month × category 的收益率中位数 DataFrame
    """
    quarter_to_months = {
        '2023-03-31': ['2023-01', '2023-02', '2023-03'],
        '2023-06-30': ['2023-04', '2023-05', '2023-06'],
        '2023-09-30': ['2023-07', '2023-08', '2023-09'],
        '2023-12-31': ['2023-10', '2023-11', '2023-12'],
        '2024-03-31': ['2024-01', '2024-02', '2024-03'],
        '2024-06-30': ['2024-04', '2024-05', '2024-06'],
        '2024-09-30': ['2024-07', '2024-08', '2024-09'],
        '2024-12-31': ['2024-10', '2024-11', '2024-12'],
        '2025-03-31': ['2025-01', '2025-02', '2025-03'],
        '2025-06-30': ['2025-04', '2025-05', '2025-06'],
        '2025-09-30': ['2025-07', '2025-08', '2025-09'],
        '2025-12-31': ['2025-10', '2025-11', '2025-12'],
    }
    month_to_quarter = {m: q for q, ms in quarter_to_months.items() for m in ms}

    monthly_ret = monthly_ret.copy()
    monthly_ret['report_date'] = monthly_ret['month'].map(month_to_quarter)
    monthly_ret = monthly_ret.dropna(subset=['report_date'])

    panel_slim = panel[['c_fd_code', 'report_date', 'category']]
    merged = monthly_ret.merge(panel_slim, on=['c_fd_code', 'report_date'], how='inner')

    median_df = (merged
                 .groupby(['month', 'category'])['ret']
                 .median()
                 .reset_index())
    return median_df.pivot(index='month', columns='category', values='ret').sort_index()


def calc_cumulative_nav(median_monthly: pd.DataFrame) -> pd.DataFrame:
    """
    从月度中位数收益率累乘为累计净值（2023-01 起始 = 1.00）
    median_monthly: month × category 收益率
    """
    cum = (1 + median_monthly.fillna(0)).cumprod()
    base = pd.DataFrame(
        {col: [1.0] for col in cum.columns},
        index=['2022-12'],
    )
    return pd.concat([base, cum])


# ── § 3 规模与机构持有 ─────────────────────────────────────────────────────────

def build_holder_panel(doris, panel: pd.DataFrame) -> pd.DataFrame:
    """
    5 半年截面机构持有规模
    返回（主代码汇总）: c_init_code, report_date,
                        inst_aum（亿元）, total_aum（亿元）,
                        inst_ratio（%，加权）
    """
    frames = []
    for rd in HALF_YEAR_DATES:
        df_holder = _fetch_holder_all_shares(doris, rd)
        if df_holder.empty:
            logger.warning(f"  {rd}: 无持有人结构数据")
            continue

        all_fd_codes = df_holder['c_fd_code'].unique().tolist()
        df_nav_unit = _fetch_nav_for_holder(doris, all_fd_codes, rd)

        if df_nav_unit.empty:
            logger.warning(f"  {rd}: 无净值数据")
            continue

        df = df_holder.merge(df_nav_unit[['c_fd_code', 'c_nav']], on='c_fd_code', how='left')
        df['c_nav'] = df['c_nav'].fillna(1.0)

        df['inst_aum_share'] = df['c_inst_share'] * df['c_nav']
        df['retail_aum_share'] = df['c_retail_share'].fillna(0) * df['c_nav']
        df['total_aum_share'] = df['inst_aum_share'] + df['retail_aum_share']

        agg = df.groupby('c_init_code').agg(
            inst_aum=('inst_aum_share', 'sum'),
            total_aum=('total_aum_share', 'sum'),
        ).reset_index()
        agg['inst_ratio'] = agg['inst_aum'] / agg['total_aum'].replace(0, float('nan')) * 100
        agg['report_date'] = rd

        agg['inst_aum'] /= 1e8
        agg['total_aum'] /= 1e8

        frames.append(agg)
        logger.info(f"  {rd}: {len(agg)} 只基金, 合计规模 {agg['total_aum'].sum():.0f} 亿")

    if not frames:
        return pd.DataFrame()

    holder_panel = pd.concat(frames, ignore_index=True)

    half_to_quarter = {
        '2023-12-31': '2023-12-31',
        '2024-06-30': '2024-06-30',
        '2024-12-31': '2024-12-31',
        '2025-06-30': '2025-06-30',
        '2025-12-31': '2025-12-31',
    }
    cat_frames = []
    for hd, qd in half_to_quarter.items():
        if qd in panel['report_date'].values:
            sub = panel[panel['report_date'] == qd][['c_fd_code', 'category']].rename(
                columns={'c_fd_code': 'c_init_code'}
            )
            sub = sub.copy()
            sub['report_date'] = hd
            cat_frames.append(sub)
    cat_panel = pd.concat(cat_frames, ignore_index=True) if cat_frames else pd.DataFrame()

    if not cat_panel.empty:
        holder_panel = holder_panel.merge(cat_panel, on=['c_init_code', 'report_date'], how='left')

    return holder_panel


def summarize_holder(holder_panel: pd.DataFrame) -> pd.DataFrame:
    """
    5 截面 × 4 分类的规模汇总（亿元）
    返回: report_date 为行，category 为列，值为总规模/机构规模
    """
    grp = holder_panel.dropna(subset=['category']).groupby(
        ['report_date', 'category']
    ).agg(
        total_aum=('total_aum', 'sum'),
        inst_aum=('inst_aum', 'sum'),
        n_funds=('c_init_code', 'count'),
        inst_ratio_median=('inst_ratio', 'median'),
    ).reset_index()
    return grp


# ── § 4 Top 基金 ──────────────────────────────────────────────────────────────

def build_fund_perf_summary(monthly_ret: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """
    每只基金的年度 + 累计收益率（仅统计全程 12 季度均在固收加面板中的基金）
    返回: c_fd_code, ret_2023, ret_2024, ret_2025, ret_total,
           category（最新一期）, c_fd_name, c_company_name, c_manager_name
    """
    # 只保留全程（12个季报截面）均在固收加池里的基金，排除中途切换类别的
    fund_quarter_cnt = panel.groupby('c_fd_code')['report_date'].nunique()
    stable_funds = fund_quarter_cnt[fund_quarter_cnt == len(QUARTER_DATES)].index
    logger.info(f"全程稳定固收加基金: {len(stable_funds)} 只（过滤前 {panel['c_fd_code'].nunique()} 只）")

    mr = monthly_ret[monthly_ret['c_fd_code'].isin(stable_funds)].copy()
    mr['year'] = mr['month'].str[:4]

    year_ret = (mr
                .groupby(['c_fd_code', 'year'])['ret']
                .apply(lambda x: (1 + x.fillna(0)).prod() - 1)
                .reset_index()
                .pivot(index='c_fd_code', columns='year', values='ret'))

    for y in ['2023', '2024', '2025']:
        if y not in year_ret.columns:
            year_ret[y] = float('nan')
    year_ret['ret_total'] = (
        (1 + year_ret['2023'].fillna(0)) *
        (1 + year_ret['2024'].fillna(0)) *
        (1 + year_ret['2025'].fillna(0)) - 1
    )

    year_ret = year_ret.rename(columns={
        '2023': 'ret_2023', '2024': 'ret_2024', '2025': 'ret_2025',
    }).reset_index()

    latest_info = (panel[panel['report_date'] == panel['report_date'].max()]
                   [['c_fd_code', 'category', 'c_fd_name', 'c_company_name', 'c_manager_name']]
                   .drop_duplicates('c_fd_code'))

    return year_ret.merge(latest_info, on='c_fd_code', how='left')


def build_size_increment(holder_panel: pd.DataFrame, fund_perf: pd.DataFrame) -> pd.DataFrame:
    """
    24-12-31 → 25-12-31 规模增量排行（只含全程稳定固收加基金）
    """
    stable_codes = set(fund_perf['c_fd_code'].dropna())

    def _get_snapshot(rd):
        return (holder_panel[
                    (holder_panel['report_date'] == rd) &
                    (holder_panel['c_init_code'].isin(stable_codes))
                ][['c_init_code', 'category', 'total_aum', 'inst_aum']]
                .rename(columns={'total_aum': f'total_{rd[:4]}',
                                 'inst_aum': f'inst_{rd[:4]}'}))

    snap_24 = _get_snapshot('2024-12-31')
    snap_25 = _get_snapshot('2025-12-31')

    if snap_24.empty or snap_25.empty:
        return pd.DataFrame()

    merged = snap_24.merge(snap_25, on='c_init_code', how='outer', suffixes=('_24', '_25'))

    merged['category'] = merged.get('category_25', pd.Series(dtype=str)).fillna(
        merged.get('category_24', pd.Series(dtype=str))
    )
    merged['total_2024'] = merged.get('total_2024', pd.Series(dtype=float)).fillna(0)
    merged['total_2025'] = merged.get('total_2025', pd.Series(dtype=float)).fillna(0)
    merged['inst_2024'] = merged.get('inst_2024', pd.Series(dtype=float)).fillna(0)
    merged['inst_2025'] = merged.get('inst_2025', pd.Series(dtype=float)).fillna(0)
    merged['delta_total'] = merged['total_2025'] - merged['total_2024']
    merged['delta_inst'] = merged['inst_2025'] - merged['inst_2024']

    perf_slim = fund_perf[['c_fd_code', 'ret_2025', 'ret_2024',
                            'c_fd_name', 'c_company_name', 'c_manager_name']]
    merged = merged.merge(
        perf_slim.rename(columns={'c_fd_code': 'c_init_code'}),
        on='c_init_code', how='left',
    )

    cols = ['c_init_code', 'category', 'c_fd_name', 'c_company_name', 'c_manager_name',
            'total_2024', 'total_2025', 'delta_total', 'inst_2024', 'inst_2025',
            'delta_inst', 'ret_2024', 'ret_2025']
    available = [c for c in cols if c in merged.columns]
    return merged[available].sort_values('delta_total', ascending=False)


# ── 输出 ──────────────────────────────────────────────────────────────────────

def export_excel(
    classification_summary,
    holder_summary,
    holder_panel,
    monthly_ret,
    panel,
    fund_perf,
    size_inc,
):
    out_path = OUT_DIR / '固收加整体分析.xlsx'
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:

        classification_summary.to_excel(writer, sheet_name='1_分类数量', index=True)

        holder_pivot = holder_summary.pivot_table(
            index='report_date', columns='category',
            values=['total_aum', 'inst_aum', 'inst_ratio_median', 'n_funds'],
            aggfunc='sum',
        )
        holder_pivot.to_excel(writer, sheet_name='2_规模汇总')

        if not holder_panel.empty and 'c_init_code' in holder_panel.columns:
            holder_wide = holder_panel.pivot_table(
                index=['c_init_code', 'category'],
                columns='report_date',
                values=['total_aum', 'inst_aum', 'inst_ratio'],
                aggfunc='first',
            ).round(2)
            holder_wide.to_excel(writer, sheet_name='3_规模明细')

        holder_panel.round(2).to_excel(writer, sheet_name='4_持有人明细', index=False)

        monthly_ret.to_excel(writer, sheet_name='5_业绩明细', index=False)

        cols_out = ['c_fd_code', 'c_fd_name', 'c_company_name', 'c_manager_name',
                    'category', 'ret_2023', 'ret_2024', 'ret_2025', 'ret_total']
        top_perf = (fund_perf[[c for c in cols_out if c in fund_perf.columns]]
                    .sort_values('ret_total', ascending=False))
        top_perf.to_excel(writer, sheet_name='6_Top业绩', index=False)

        size_inc_out = size_inc.head(100) if not size_inc.empty else size_inc
        size_inc_out.to_excel(writer, sheet_name='7_Top规模增量', index=False)

        migration = panel[['c_fd_code', 'c_fd_name', 'report_date', 'category']].copy()
        migration_wide = migration.pivot_table(
            index=['c_fd_code', 'c_fd_name'], columns='report_date',
            values='category', aggfunc='first',
        )
        migration_wide.to_excel(writer, sheet_name='8_分类迁移')

    logger.info(f"Excel 已保存至 {out_path}")
    return out_path


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run():
    import charts

    with DorisConnector(ENV) as doris:
        logger.info("=== § 1 样本分类 ===")
        panel = build_classification_panel(doris)
        cls_summary = summarize_classification(panel)
        logger.info(f"\n{cls_summary}")

        logger.info("=== § 2 业绩走势 ===")
        monthly_ret = build_monthly_returns(doris, panel)
        median_df = calc_category_monthly_median(monthly_ret, panel)
        cum_nav = calc_cumulative_nav(median_df)

        logger.info("=== § 3 规模与机构持有 ===")
        holder_panel = build_holder_panel(doris, panel)
        holder_summary = summarize_holder(holder_panel)

        logger.info("=== § 4 Top 基金 ===")
        fund_perf = build_fund_perf_summary(monthly_ret, panel)
        size_inc = build_size_increment(holder_panel, fund_perf)

    logger.info("=== 输出图表 ===")
    charts.plot_category_count(cls_summary)
    charts.plot_monthly_median_return(median_df)
    charts.plot_cumulative_nav(cum_nav)
    charts.plot_annual_boxplot(fund_perf)
    charts.plot_size_by_category(holder_summary)
    charts.plot_inst_size_by_category(holder_summary)
    charts.plot_inst_ratio_trend(holder_summary)
    charts.plot_delta_bar(size_inc)
    charts.plot_size_vs_ret(size_inc)
    logger.info("图表已保存至 images/")

    logger.info("=== 输出 Excel ===")
    export_excel(cls_summary, holder_summary, holder_panel,
                 monthly_ret, panel, fund_perf, size_inc)

    logger.info("=== 完成 ===")


if __name__ == '__main__':
    run()

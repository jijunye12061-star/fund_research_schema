"""
固收+基金 Brinson 大类资产收益归因

流程:
  Step 1  每季度固收+基金池 → 波动率分类(低/中/高/转债)
  Step 2  基于持仓模拟各资产组合收益 → Brinson 归因分解
  Step 3  八季度简单加总 → 输出每基金一行的归因表

输出列: 基金代码 | 基金名称 | 类型 | 绝对收益 | 超额收益 | 配置收益 | 选券收益 |
        交易收益 | 实际转债仓位归一化收益率 | 实际股票仓位归一化收益率 |
        转债投资战胜指数胜率 | 转债投资正收益概率
"""
from pathlib import Path

import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

# ══════════════════════════════════════════════════════════════════════════════
#  参数配置（按需修改）
# ══════════════════════════════════════════════════════════════════════════════

# 分析期间
PERIOD_START = '2024-02-08'
PERIOD_END = '2026-01-27'

# 重定义季度: 季报日前后各 45 天
QUARTERS = [
    {'start': '2024-02-08', 'end': '2024-05-15', 'report': '2024-03-31'},
    {'start': '2024-05-16', 'end': '2024-08-15', 'report': '2024-06-30'},
    {'start': '2024-08-16', 'end': '2024-11-15', 'report': '2024-09-30'},
    {'start': '2024-11-16', 'end': '2025-02-13', 'report': '2024-12-31'},
    {'start': '2025-02-14', 'end': '2025-05-15', 'report': '2025-03-31'},
    {'start': '2025-05-16', 'end': '2025-08-15', 'report': '2025-06-30'},
    {'start': '2025-08-16', 'end': '2025-11-15', 'report': '2025-09-30'},
    {'start': '2025-11-16', 'end': '2026-01-27', 'report': '2025-12-31'},
]

# 基准指数
IDX_STK = '000300'      # 沪深300
IDX_CB = '000832'       # 中证转债
IDX_BD = 'CBA00101'     # 中债新综合财富指数

# 分类阈值
LOW_VOL_EQUITY_THRESH = 5.0    # 含权仓位 < 5% → 低波
HIGH_VOL_STK_THRESH = 40.0     # 股票仓位 > 40% → 高波

# ══════════════════════════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════════════════════════

def _hold_style(report_date: str) -> str:
    """持仓表 c_style（06-30/12-31 优先全持仓）"""
    m = report_date[5:7]
    return {'03': '01', '06': '02', '09': '03', '12': '04'}[m]


def _alloc_style(report_date: str) -> str:
    """资产配置表 c_style（季报级）"""
    m = report_date[5:7]
    return {'03': '01', '06': '05', '09': '03', '12': '06'}[m]


def _lookback_dates(report_date: str, n: int = 4) -> list:
    """返回包含当期在内的近 n 期季度报告期"""
    y = int(report_date[:4])
    q_dates = []
    for year in range(y - 2, y + 1):
        for mm, dd in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            q_dates.append(f"{year}-{mm:02d}-{dd:02d}")
    q_dates = [d for d in q_dates if d <= report_date]
    return q_dates[-n:]


def _get_trade_date(doris, date: str) -> str:
    """报告期 → 最近交易日"""
    df = doris.query(
        "SELECT c_max_trade_date FROM tb_trade_calendar WHERE c_date = :d",
        d=date,
    )
    return str(df.iloc[0]['c_max_trade_date'])[:10] if not df.empty else date


def _weighted_avg(weights, returns):
    """加权平均收益率，权重归一化"""
    w = np.array(weights, dtype=float)
    r = np.array(returns, dtype=float)
    total = w.sum()
    if total <= 0:
        return 0.0
    return float((w * r).sum() / total)


# ══════════════════════════════════════════════════════════════════════════════
#  数据获取
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_universe(doris, report_date: str) -> pd.DataFrame:
    """获取固收+基金池：官方分类一级债基+二级债基，主代码去重"""
    sql = """
    SELECT b.c_fd_code,
           COALESCE(f.c_type2_code, '') AS c_type2_code,
           b.c_short_name AS c_fd_name,
           CASE WHEN b.c_class3_code = '003002001' THEN '混合债券型一级基金'
                WHEN b.c_class3_code = '003002002' THEN '混合债券型二级基金'
           END AS c_fd_type
    FROM tb_fd_basic_info b
    LEFT JOIN tb_fd_category f
           ON f.c_fd_code = b.c_fd_code AND f.c_report_date = :report_date
    WHERE b.c_class3_code IN ('003002001', '003002002')
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND b.c_terminate_date IS NULL
    """
    return doris.query(sql, report_date=report_date)


def _fetch_alloc(doris, fd_codes: list, report_dates: list) -> pd.DataFrame:
    """批量获取多期资产配置"""
    frames = []
    for rd in report_dates:
        sql = """
        SELECT c_fd_code, c_report_date,
               COALESCE(c_stk_total_ratio, 0) AS c_stk_ratio,
               COALESCE(c_bd_convertible_ratio, 0) AS c_cb_ratio,
               COALESCE(c_bd_total_ratio, 0) AS c_bd_ratio
        FROM tb_fd_asset_allocation
        WHERE c_report_date = :report_date
          AND c_style = :c_style
          AND c_fd_code IN (:code_list)
        """
        df = doris.query_batch(sql, fd_codes,
                               report_date=rd, c_style=_alloc_style(rd))
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_perf(doris, fd_codes: list, trade_date: str) -> pd.DataFrame:
    """获取近 1 年波动率和最大回撤"""
    sql = """
    SELECT c_fd_code, c_ann_vol, c_mdd
    FROM tb_fd_perform_abs
    WHERE c_period_code = '03'
      AND c_trade_date = :trade_date
      AND c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes, trade_date=trade_date)


def _fetch_stk_hold(doris, fd_codes: list, report_date: str) -> pd.DataFrame:
    """获取股票持仓（季报前十大 / 半年报全量）"""
    sql = """
    SELECT c_fd_code, c_stk_code,
           COALESCE(c_nav_ratio, 0) AS c_nav_ratio
    FROM tb_fd_portfolio_stk
    WHERE c_report_date = :report_date
      AND c_style = :c_style
      AND c_fd_code IN (:code_list)
      AND c_nav_ratio IS NOT NULL AND c_nav_ratio > 0
    """
    return doris.query_batch(sql, fd_codes,
                             report_date=report_date, c_style=_hold_style(report_date))


def _fetch_cb_hold(doris, fd_codes: list, report_date: str) -> pd.DataFrame:
    """获取转债持仓（含转股期 + 非转股期可转债/可交换债）"""
    st = _hold_style(report_date)
    # 先取全部债券持仓
    sql_all = """
    SELECT c_fd_code, c_bd_code, c_bd_inner_code, c_bd_type,
           COALESCE(c_nav_ratio, 0) AS c_nav_ratio
    FROM tb_fd_portfolio_bd
    WHERE c_report_date = :report_date
      AND c_style = :c_style
      AND c_fd_code IN (:code_list)
      AND c_nav_ratio IS NOT NULL AND c_nav_ratio > 0
    """
    df = doris.query_batch(sql_all, fd_codes,
                           report_date=report_date, c_style=st)
    if df.empty:
        return df[['c_fd_code', 'c_bd_code', 'c_nav_ratio']].head(0)

    # 方式1: portfolio 表 c_bd_type='2' 即转股期转债
    is_cb = df['c_bd_type'] == '2'

    # 方式2: 通过 basic_info 补充非转股期转债
    non_cb_df = df[~is_cb]
    if not non_cb_df.empty:
        inner_codes = non_cb_df['c_bd_inner_code'].dropna().unique().tolist()
        if inner_codes:
            sql_check = """
            SELECT c_bd_inner_code
            FROM tb_bd_basic_info
            WHERE c_bd_inner_code IN (:code_list)
              AND c_bd_type IN ('可转换债券', '可交换债券', '可分离交易可转债')
            """
            cb_basic = doris.query_batch(sql_check, inner_codes)
            if not cb_basic.empty:
                cb_inner_set = set(cb_basic['c_bd_inner_code'])
                is_cb = is_cb | df['c_bd_inner_code'].isin(cb_inner_set)

    result = df.loc[is_cb, ['c_fd_code', 'c_bd_code', 'c_nav_ratio']].copy()
    # 同一只转债可能同时以 c_bd_type='1' 和 '2' 出现（数据源双报），按(基金,债券)去重取最大值
    result = (result
              .groupby(['c_fd_code', 'c_bd_code'], as_index=False)['c_nav_ratio']
              .max())
    return result


def _fetch_stk_daily(doris, stk_codes: list, start: str, end: str) -> pd.DataFrame:
    """获取股票日涨跌幅（%）"""
    sql = """
    SELECT c_trade_date, c_stk_code, c_pct_chg
    FROM tb_stk_quote_daily
    WHERE c_trade_date >= :start_date AND c_trade_date <= :end_date
      AND c_stk_code IN (:code_list)
    """
    return doris.query_batch(sql, stk_codes,
                             start_date=start, end_date=end)


def _fetch_cb_daily(doris, bd_codes: list, start: str, end: str) -> pd.DataFrame:
    """获取转债日全价"""
    sql = """
    SELECT c_trade_date, c_bd_code, c_full_close, c_full_pre_close
    FROM tb_bd_quote_daily
    WHERE c_trade_date >= :start_date AND c_trade_date <= :end_date
      AND c_bd_code IN (:code_list)
      AND c_full_close IS NOT NULL AND c_full_close > 0
    """
    return doris.query_batch(sql, bd_codes,
                             start_date=start, end_date=end)


def _fetch_idx_daily(doris, start: str, end: str) -> pd.DataFrame:
    """获取三个基准指数日行情"""
    sql = """
    SELECT c_trade_date, c_idx_code, c_close, c_pre_close
    FROM tb_idx_quote_daily
    WHERE c_trade_date >= :start_date AND c_trade_date <= :end_date
      AND c_idx_code IN (:i1, :i2, :i3)
    ORDER BY c_trade_date
    """
    return doris.query(sql, start_date=start, end_date=end,
                       i1=IDX_STK, i2=IDX_CB, i3=IDX_BD)


def _fetch_nav_daily(doris, fd_codes: list, start: str, end: str) -> pd.DataFrame:
    """获取基金复权净值"""
    sql = """
    SELECT c_trade_date, c_fd_code, c_nav_adj
    FROM tb_fd_nav_daily
    WHERE c_trade_date >= :start_date AND c_trade_date <= :end_date
      AND c_fd_code IN (:code_list)
      AND c_nav_adj IS NOT NULL AND c_nav_adj > 0
    """
    return doris.query_batch(sql, fd_codes,
                             start_date=start, end_date=end)


# ══════════════════════════════════════════════════════════════════════════════
#  分类逻辑
# ══════════════════════════════════════════════════════════════════════════════

def _classify(df_univ: pd.DataFrame,
              df_alloc_4q: pd.DataFrame,
              df_perf: pd.DataFrame) -> pd.DataFrame:
    """
    固收+基金波动分类（单季度截面）
    返回 DataFrame[c_fd_code, vol_type]
    """
    results = []

    # ── 转债基金直接归类 ──
    cb_funds = df_univ.loc[df_univ['c_type2_code'] == '002001', 'c_fd_code'].tolist()
    results.extend({'c_fd_code': fd, 'vol_type': '可转债基金'} for fd in cb_funds)

    # ── 其余基金 ──
    other_codes = df_univ.loc[df_univ['c_type2_code'] != '002001', 'c_fd_code']
    if other_codes.empty or df_alloc_4q.empty:
        return pd.DataFrame(results)

    # 近一期仓位
    latest_rd = df_alloc_4q['c_report_date'].max()
    alloc_cur = (df_alloc_4q[df_alloc_4q['c_report_date'] == latest_rd]
                 .set_index('c_fd_code')[['c_stk_ratio', 'c_cb_ratio']])
    other = other_codes.to_frame().merge(alloc_cur, on='c_fd_code', how='left')
    other['c_stk_ratio'] = other['c_stk_ratio'].fillna(0)
    other['c_cb_ratio'] = other['c_cb_ratio'].fillna(0)
    other['equity_exp'] = other['c_stk_ratio'] + other['c_cb_ratio'] / 2

    # ── 低波: 含权仓位 < 5% ──
    low_mask = other['equity_exp'] < LOW_VOL_EQUITY_THRESH
    results.extend({'c_fd_code': fd, 'vol_type': '低波固收+'}
                   for fd in other.loc[low_mask, 'c_fd_code'])

    # ── 高波: 股票 > 40% ──
    high_mask = (~low_mask) & (other['c_stk_ratio'] > HIGH_VOL_STK_THRESH)
    results.extend({'c_fd_code': fd, 'vol_type': '高波固收+'}
                   for fd in other.loc[high_mask, 'c_fd_code'])

    # ── 核心样本: 排名 → 1:1:1 ──
    core_mask = ~(low_mask | high_mask)
    core = other[core_mask].copy()
    if core.empty:
        return pd.DataFrame(results)

    core = core.merge(df_perf[['c_fd_code', 'c_ann_vol', 'c_mdd']],
                      on='c_fd_code', how='left')
    core['c_ann_vol'] = core['c_ann_vol'].fillna(core['c_ann_vol'].median())
    core['c_mdd'] = core['c_mdd'].fillna(core['c_mdd'].median())

    # 三指标百分位排名（越大 → 越"高波"）
    core['rank_eq'] = core['equity_exp'].rank(pct=True)
    core['rank_vol'] = core['c_ann_vol'].rank(pct=True)
    core['rank_mdd'] = core['c_mdd'].rank(pct=True)
    core['composite'] = (core['rank_eq'] + core['rank_vol'] + core['rank_mdd']) / 3

    # 等分三组
    try:
        core['vol_type'] = pd.qcut(core['composite'], q=3,
                                   labels=['低波固收+', '中波固收+', '高波固收+'])
    except ValueError:
        # 样本太少或分位数重合时退化处理
        n = len(core)
        t = n // 3
        core = core.sort_values('composite')
        labels = ['低波固收+'] * t + ['中波固收+'] * t + ['高波固收+'] * (n - 2 * t)
        core['vol_type'] = labels

    results.extend(core[['c_fd_code', 'vol_type']].to_dict('records'))
    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
#  基准权重
# ══════════════════════════════════════════════════════════════════════════════

def _benchmark_weights(df_alloc_4q: pd.DataFrame,
                       df_class: pd.DataFrame) -> dict:
    """
    每类基金近四期平均仓位 → 归一化为基准权重
    返回 {vol_type: {w_stk, w_cb, w_bd}}
    """
    merged = df_alloc_4q.merge(df_class[['c_fd_code', 'vol_type']], on='c_fd_code')
    merged['c_pure_bd'] = (merged['c_bd_ratio'] - merged['c_cb_ratio']).clip(lower=0)

    avg = merged.groupby('vol_type')[['c_stk_ratio', 'c_cb_ratio', 'c_pure_bd']].mean()
    total = avg.sum(axis=1).replace(0, 1)  # 防除零

    bw = {}
    for vt in avg.index:
        bw[vt] = {
            'w_stk': avg.loc[vt, 'c_stk_ratio'] / total[vt],
            'w_cb':  avg.loc[vt, 'c_cb_ratio']  / total[vt],
            'w_bd':  avg.loc[vt, 'c_pure_bd']   / total[vt],
        }
    return bw


# ══════════════════════════════════════════════════════════════════════════════
#  收益率计算
# ══════════════════════════════════════════════════════════════════════════════

def _calc_stk_ret(df_hold: pd.DataFrame, df_daily: pd.DataFrame) -> pd.Series:
    """每只基金的股票组合季度收益率（按持仓权重加权）"""
    if df_hold.empty or df_daily.empty:
        return pd.Series(dtype=float, name='rp_stk')

    # 每只股票季度复合收益率
    stk_ret = (df_daily
               .groupby('c_stk_code')['c_pct_chg']
               .apply(lambda x: (1 + x.fillna(0) / 100).prod() - 1))

    hold = df_hold.merge(stk_ret.rename('ret').reset_index(),
                         on='c_stk_code', how='left')
    hold['ret'] = hold['ret'].fillna(0)

    return (hold
            .groupby('c_fd_code')
            .apply(lambda g: _weighted_avg(g['c_nav_ratio'], g['ret']),
                   include_groups=False)
            .rename('rp_stk'))


def _calc_cb_ret(df_hold: pd.DataFrame, df_daily: pd.DataFrame) -> pd.Series:
    """每只基金的转债组合季度收益率（全价首尾比）"""
    if df_hold.empty or df_daily.empty:
        return pd.Series(dtype=float, name='rp_cb')

    # 每只转债: 全价日收益率 → 复合
    df_daily = df_daily.sort_values('c_trade_date')
    cb_ret = (df_daily
              .groupby('c_bd_code')
              .apply(lambda g: g['c_full_close'].iloc[-1] / g['c_full_close'].iloc[0] - 1
                     if len(g) >= 2 and g['c_full_close'].iloc[0] > 0 else 0.0,
                     include_groups=False))

    hold = df_hold.merge(cb_ret.rename('ret').reset_index(),
                         on='c_bd_code', how='left')
    hold['ret'] = hold['ret'].fillna(0)

    return (hold
            .groupby('c_fd_code')
            .apply(lambda g: _weighted_avg(g['c_nav_ratio'], g['ret']),
                   include_groups=False)
            .rename('rp_cb'))


def _calc_idx_ret(df_daily: pd.DataFrame) -> dict:
    """三个基准指数的季度收益率"""
    result = {}
    for idx in [IDX_STK, IDX_CB, IDX_BD]:
        sub = df_daily[df_daily['c_idx_code'] == idx].sort_values('c_trade_date')
        if len(sub) >= 2:
            result[idx] = (sub['c_close'] / sub['c_pre_close']).prod() - 1
        else:
            result[idx] = 0.0
    return result


def _calc_fund_ret(df_nav: pd.DataFrame) -> pd.Series:
    """每只基金季度实际收益率（复权净值首尾比）"""
    if df_nav.empty:
        return pd.Series(dtype=float, name='rp')
    df_nav = df_nav.sort_values('c_trade_date')
    return (df_nav
            .groupby('c_fd_code')['c_nav_adj']
            .apply(lambda g: g.iloc[-1] / g.iloc[0] - 1
                   if len(g) >= 2 and g.iloc[0] > 0 else 0.0)
            .rename('rp'))


# ══════════════════════════════════════════════════════════════════════════════
#  Brinson 归因（单季度）
# ══════════════════════════════════════════════════════════════════════════════

def _brinson_quarter(fund_rets: pd.Series,
                     stk_rets: pd.Series,
                     cb_rets: pd.Series,
                     idx_rets: dict,
                     df_alloc_cur: pd.DataFrame,
                     df_class: pd.DataFrame,
                     bench_w: dict,
                     report_date: str) -> pd.DataFrame:
    """单季度 Brinson 大类资产归因"""
    alloc_idx = df_alloc_cur.set_index('c_fd_code')
    class_idx = df_class.set_index('c_fd_code')['vol_type']
    rb_s, rb_cb, rb_b = idx_rets[IDX_STK], idx_rets[IDX_CB], idx_rets[IDX_BD]

    rows = []
    for fd in fund_rets.index:
        if fd not in class_idx.index:
            continue
        vt = class_idx[fd]
        bw = bench_w.get(vt)
        if bw is None:
            continue

        # ── 组合权重（归一化：股票+转债+纯债=1）──
        if fd in alloc_idx.index:
            w_s = float(alloc_idx.loc[fd, 'c_stk_ratio'])
            w_cb = float(alloc_idx.loc[fd, 'c_cb_ratio'])
            w_bd_raw = float(alloc_idx.loc[fd, 'c_bd_ratio']) - w_cb
        else:
            w_s = w_cb = 0.0
            w_bd_raw = 100.0
        w_bd_raw = max(w_bd_raw, 0)
        total_w = w_s + w_cb + w_bd_raw
        if total_w <= 0:
            continue
        wp_s = w_s / total_w
        wp_cb = w_cb / total_w
        wp_b = w_bd_raw / total_w

        # ── 基准权重 ──
        wb_s, wb_cb, wb_b = bw['w_stk'], bw['w_cb'], bw['w_bd']

        # ── 各资产收益率 ──
        rp = float(fund_rets.get(fd, 0))
        rp_s = float(stk_rets.get(fd, 0))
        rp_cb = float(cb_rets.get(fd, 0))
        # 纯债 = 残差
        rp_b = (rp - wp_s * rp_s - wp_cb * rp_cb) / wp_b if wp_b > 0 else 0.0

        # ── Brinson 四组合 ──
        r1 = rp                                                  # 实际收益
        r2 = wp_cb * rb_cb + wp_s * rb_s + wp_b * rb_b          # 组合权重×基准收益
        r3 = wb_cb * rp_cb + wb_s * rp_s + wb_b * rp_b          # 基准权重×组合收益
        r4 = wb_cb * rb_cb + wb_s * rb_s + wb_b * rb_b          # 基准权重×基准收益

        has_cb = w_cb > 0.5  # 转债仓位 > 0.5% 视为有转债

        rows.append({
            'c_fd_code': fd,
            'vol_type': vt,
            'report_date': report_date,
            'abs_ret': r1,
            'excess_ret': r1 - r4,
            'alloc_ret': r2 - r4,
            'select_ret': r3 - r4,
            'trade_ret': r1 - r2 - r3 + r4,
            'rp_cb': rp_cb,
            'rp_stk': rp_s,
            'has_cb': has_cb,
            'cb_beat_idx': (rp_cb > rb_cb) if has_cb else None,
            'cb_positive': (rp_cb > 0) if has_cb else None,
            # 基准收益存档
            'bench_ret': r4,
            'rb_stk': rb_s,
            'rb_cb': rb_cb,
            'rb_bd': rb_b,
            'wp_stk': wp_s,
            'wp_cb': wp_cb,
            'wp_bd': wp_b,
        })

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  汇总
# ══════════════════════════════════════════════════════════════════════════════

def _aggregate(qr_list: list, doris) -> pd.DataFrame:
    """八季度归因结果汇总"""
    all_df = pd.concat(qr_list, ignore_index=True)

    # 剔除近8期股票+转债权重全为0的基金
    has_equity = (all_df.groupby('c_fd_code')
                  .apply(lambda g: ((g['wp_stk'] + g['wp_cb']) > 0).any()))
    all_df = all_df[all_df['c_fd_code'].isin(has_equity[has_equity].index)]

    # ── 收益率列简单加总 ──
    sum_cols = ['abs_ret', 'excess_ret', 'alloc_ret', 'select_ret',
                'trade_ret', 'rp_cb', 'rp_stk']
    agg = all_df.groupby('c_fd_code')[sum_cols].sum()

    # ── 最新一期分类 ──
    latest = qr_list[-1].drop_duplicates('c_fd_code').set_index('c_fd_code')
    agg['vol_type'] = latest['vol_type']

    # ── 转债胜率 ──
    cb_df = all_df[all_df['has_cb'] == True]
    if not cb_df.empty:
        cb_grp = cb_df.groupby('c_fd_code')
        agg['cb_win_rate'] = cb_grp['cb_beat_idx'].mean()
        agg['cb_pos_rate'] = cb_grp['cb_positive'].mean()
    else:
        agg['cb_win_rate'] = np.nan
        agg['cb_pos_rate'] = np.nan

    # ── 基金名称 + 官方基金类型 ──
    last_report = QUARTERS[-1]['report']
    df_names = _fetch_universe(doris, last_report)[['c_fd_code', 'c_fd_name', 'c_fd_type']]
    agg = agg.reset_index().merge(df_names, on='c_fd_code', how='left')

    return agg


# ══════════════════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════════════════

def run():
    with DorisConnector(ENV) as doris:
        quarter_results = []
        bench_w_log = []  # 记录每季度基准权重

        for i, q in enumerate(QUARTERS):
            rd = q['report']
            logger.info(f"== Q{i+1}/8  {rd}  ({q['start']} ~ {q['end']}) ==")

            # 1) 基金池
            df_univ = _fetch_universe(doris, rd)
            fd_codes = df_univ['c_fd_code'].tolist()
            if not fd_codes:
                logger.warning(f"  报告期 {rd} 无固收+基金数据，跳过")
                continue
            logger.info(f"  基金池 {len(fd_codes)} 只")

            # 2) 近四期资产配置
            lb_dates = _lookback_dates(rd, 4)
            df_alloc_4q = _fetch_alloc(doris, fd_codes, lb_dates)

            # 3) 分类
            td = _get_trade_date(doris, rd)
            df_perf = _fetch_perf(doris, fd_codes, td)
            df_class = _classify(df_univ, df_alloc_4q, df_perf)
            if df_class.empty:
                continue
            vc = df_class['vol_type'].value_counts().to_dict()
            logger.info(f"  分类 {vc}")

            # 4) 基准权重
            bw = _benchmark_weights(df_alloc_4q, df_class)
            for vt, w in bw.items():
                bench_w_log.append({
                    'report_date': rd, 'vol_type': vt,
                    'w_stk': w['w_stk'], 'w_cb': w['w_cb'], 'w_bd': w['w_bd'],
                })
            logger.info(f"  基准权重 {({k: {kk: round(vv,4) for kk,vv in v.items()} for k,v in bw.items()})}")

            # 5) 持仓
            classified_codes = df_class['c_fd_code'].tolist()
            df_stk_hold = _fetch_stk_hold(doris, classified_codes, rd)
            df_cb_hold = _fetch_cb_hold(doris, classified_codes, rd)
            logger.info(f"  持仓: 股票 {df_stk_hold['c_stk_code'].nunique()} 只, "
                        f"转债 {df_cb_hold['c_bd_code'].nunique() if not df_cb_hold.empty else 0} 只")

            # 6) 行情数据
            stk_codes = df_stk_hold['c_stk_code'].unique().tolist() if not df_stk_hold.empty else []
            cb_codes = df_cb_hold['c_bd_code'].unique().tolist() if not df_cb_hold.empty else []

            df_stk_daily = _fetch_stk_daily(doris, stk_codes, q['start'], q['end']) if stk_codes else pd.DataFrame()
            df_cb_daily = _fetch_cb_daily(doris, cb_codes, q['start'], q['end']) if cb_codes else pd.DataFrame()
            df_idx_daily = _fetch_idx_daily(doris, q['start'], q['end'])
            df_nav_daily = _fetch_nav_daily(doris, classified_codes, q['start'], q['end'])

            # 7) 各资产收益
            stk_port_rets = _calc_stk_ret(df_stk_hold, df_stk_daily)
            cb_port_rets = _calc_cb_ret(df_cb_hold, df_cb_daily)
            idx_rets = _calc_idx_ret(df_idx_daily)
            fund_rets = _calc_fund_ret(df_nav_daily)
            logger.info(f"  指数收益 沪深300={idx_rets[IDX_STK]:.4f} "
                        f"中证转债={idx_rets[IDX_CB]:.4f} "
                        f"中债新综合={idx_rets[IDX_BD]:.4f}")

            # 8) 当期配置（Brinson 组合权重）
            # c_report_date 从 DB 读出为 'YYYY-MM-DD HH:MM:SS' 字符串，需截取前10位再比较
            df_alloc_cur = df_alloc_4q[
                df_alloc_4q['c_report_date'].astype(str).str[:10] == rd
            ].copy()

            # 9) 归因
            qr = _brinson_quarter(fund_rets, stk_port_rets, cb_port_rets,
                                  idx_rets, df_alloc_cur, df_class, bw, rd)
            quarter_results.append(qr)
            logger.info(f"  归因完成 {len(qr)} 只基金")

        if not quarter_results:
            logger.error("无任何季度数据，终止")
            return pd.DataFrame()

        # ── 汇总 ──
        final = _aggregate(quarter_results, doris)

        # ── 输出 ──
        out_path = Path(__file__).parent / 'data' / '固收加收益归因.xlsx'
        out_path.parent.mkdir(exist_ok=True)

        # 格式化（保留小数形式，与参考文件一致；胜率保持 0~1）
        ret_cols = ['abs_ret', 'excess_ret', 'alloc_ret', 'select_ret',
                    'trade_ret', 'rp_cb', 'rp_stk']
        for c in ret_cols:
            final[c] = final[c].round(6)
        for c in ['cb_win_rate', 'cb_pos_rate']:
            if c in final.columns:
                final[c] = pd.to_numeric(final[c], errors='coerce').round(4)

        # 派生波动程度列（低/中/高，可转债基金留空）
        vol_map = {'低波固收+': '低', '中波固收+': '中', '高波固收+': '高', '可转债基金': ''}
        final['vol_level'] = final['vol_type'].map(vol_map).fillna('')

        col_rename = {
            'c_fd_code': '证券代码', 'c_fd_name': '基金简称', 'c_fd_type': '基金类型',
            'vol_type': '分类', 'vol_level': '波动程度',
            'abs_ret': '绝对收益', 'excess_ret': '超额收益',
            'alloc_ret': '配置收益', 'select_ret': '选券收益', 'trade_ret': '交易收益',
            'rp_cb': '实际转债仓位归一化收益率', 'rp_stk': '实际股票仓位归一化收益率',
            'cb_win_rate': '转债投资战胜指数胜率', 'cb_pos_rate': '转债投资正收益概率',
        }
        out_cols = list(col_rename.keys())
        final_out = final[[c for c in out_cols if c in final.columns]].rename(columns=col_rename)

        # 季度明细
        detail = pd.concat(quarter_results, ignore_index=True)
        detail_pct = detail.copy()
        for c in ret_cols:
            if c in detail_pct.columns:
                detail_pct[c] = detail_pct[c].round(6)

        # 基准权重
        df_bw = pd.DataFrame(bench_w_log)
        for c in ['w_stk', 'w_cb', 'w_bd']:
            df_bw[c] = (df_bw[c] * 100).round(2)

        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            final_out.to_excel(writer, sheet_name='归因汇总', index=False)
            detail_pct.to_excel(writer, sheet_name='季度明细', index=False)
            df_bw.to_excel(writer, sheet_name='基准权重', index=False)

        logger.info(f"已保存至 {out_path}")
        logger.info(f"共 {len(final_out)} 只基金, {len(quarter_results)} 个季度")
        return final


if __name__ == '__main__':
    run()

"""
固收加基金整体分析 — 图表模块
接收 analyze.py 传入的 DataFrame，输出 PNG 到 images/
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

# 直接注册字体文件，绕过缓存索引的名称查找问题
_FONT_FILES = [
    Path(r'C:\Windows\Fonts\simhei.ttf'),
    Path(r'C:\Windows\Fonts\msyh.ttc'),    # Microsoft YaHei
    Path(r'C:\Windows\Fonts\simsun.ttc'),
]
for _f in _FONT_FILES:
    if _f.exists():
        fm.fontManager.addfont(str(_f))

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

IMG_DIR = Path(__file__).parent / 'images'
IMG_DIR.mkdir(exist_ok=True)

# 四分类颜色
CAT_COLORS = {
    '转债基金': '#E07B54',
    '稳健': '#5B9BD5',
    '均衡': '#70AD47',
    '激进': '#ED7D31',
}
CAT_ORDER = ['稳健', '均衡', '激进', '转债基金']

# 从 analyze 模块引用的常量（延迟导入避免循环）
HALF_YEAR_DATES = [
    '2023-12-31', '2024-06-30', '2024-12-31',
    '2025-06-30', '2025-12-31',
]


def plot_category_count(classification_summary) -> 'Path':
    """各分类基金数量堆叠面积图"""
    fig, ax = plt.subplots(figsize=(12, 5))
    cats = [c for c in ['稳健', '均衡', '激进', '转债基金'] if c in classification_summary.columns]
    data = classification_summary[cats].fillna(0)
    ax.stackplot(data.index, [data[c] for c in cats],
                 labels=cats,
                 colors=[CAT_COLORS[c] for c in cats],
                 alpha=0.8)
    ax.set_title('固收加基金数量分布（季报截面）', fontsize=14)
    ax.set_ylabel('基金数量（只）')
    ax.set_xlabel('报告期')
    ax.tick_params(axis='x', rotation=45)
    ax.legend(loc='upper left')
    plt.tight_layout()
    path = IMG_DIR / '1.1_category_count.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_monthly_median_return(median_df) -> 'Path':
    """月度中位数收益率折线"""
    fig, ax = plt.subplots(figsize=(14, 5))
    cats = [c for c in CAT_ORDER if c in median_df.columns]
    for cat in cats:
        ax.plot(range(len(median_df)), median_df[cat] * 100,
                label=cat, color=CAT_COLORS[cat], linewidth=1.5)
    ax.axhline(0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_xticks(range(len(median_df)))
    ax.set_xticklabels(list(median_df.index), rotation=90, fontsize=7)
    ax.set_ylabel('月度中位数收益率（%）')
    ax.set_title('固收加基金月度收益率中位数（2023-2025）', fontsize=14)
    ax.legend()
    ax.axvspan(0, 23, alpha=0.05, color='blue')
    ax.axvspan(24, 35, alpha=0.05, color='red')
    plt.tight_layout()
    path = IMG_DIR / '2.1_monthly_median_ret.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_cumulative_nav(cum_nav) -> 'Path':
    """累计净值曲线"""
    fig, ax = plt.subplots(figsize=(14, 5))
    cats = [c for c in CAT_ORDER if c in cum_nav.columns]
    for cat in cats:
        ax.plot(range(len(cum_nav)), cum_nav[cat],
                label=cat, color=CAT_COLORS[cat], linewidth=2)
    ax.axhline(1.0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_xticks(range(len(cum_nav)))
    ax.set_xticklabels(list(cum_nav.index), rotation=90, fontsize=7)
    ax.set_ylabel('累计净值（2023年初 = 1.00）')
    ax.set_title('固收加基金累计净值（2023-2025）', fontsize=14)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '2.2_cumulative_nav.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_annual_boxplot(fund_perf) -> 'Path':
    """年度收益箱线图"""
    years = ['ret_2023', 'ret_2024', 'ret_2025']
    year_labels = ['2023', '2024', '2025']
    cats = CAT_ORDER
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
    for i, (yr, yl) in enumerate(zip(years, year_labels)):
        ax = axes[i]
        data = [fund_perf[fund_perf['category'] == c][yr].dropna() * 100
                for c in cats if 'category' in fund_perf.columns]
        if not data or all(len(d) == 0 for d in data):
            ax.set_title(f'{yl}年收益分布（无数据）', fontsize=12)
            continue
        bp = ax.boxplot(data, labels=cats, patch_artist=True,
                        medianprops={'color': 'black', 'linewidth': 2})
        for patch, cat in zip(bp['boxes'], cats):
            patch.set_facecolor(CAT_COLORS[cat])
            patch.set_alpha(0.7)
        ax.set_title(f'{yl}年收益分布', fontsize=12)
        ax.set_ylabel('收益率（%）')
        ax.tick_params(axis='x', rotation=30)
        ax.axhline(0, color='gray', linestyle='--', linewidth=0.5)
    plt.suptitle('固收加基金年度收益分布', fontsize=14)
    plt.tight_layout()
    path = IMG_DIR / '2.3_annual_boxplot.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_size_by_category(holder_summary) -> 'Path':
    """分类总规模堆叠柱状图"""
    dates = HALF_YEAR_DATES
    pivot_total = (holder_summary
                   .pivot_table(index='report_date', columns='category', values='total_aum', aggfunc='sum')
                   .reindex(dates).fillna(0))
    cats = [c for c in CAT_ORDER if c in pivot_total.columns]
    x = range(len(dates))
    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = [0.0] * len(dates)
    for cat in cats:
        vals = pivot_total[cat].values
        ax.bar(x, vals, bottom=bottom, label=cat, color=CAT_COLORS[cat], alpha=0.85)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, rotation=30)
    ax.set_ylabel('总规模（亿元）')
    ax.set_title('固收加基金规模（半年截面）', fontsize=14)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '3.1_size_by_category.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_inst_size_by_category(holder_summary) -> 'Path':
    """机构持有规模堆叠柱状图"""
    dates = HALF_YEAR_DATES
    pivot_inst = (holder_summary
                  .pivot_table(index='report_date', columns='category', values='inst_aum', aggfunc='sum')
                  .reindex(dates).fillna(0))
    cats = [c for c in CAT_ORDER if c in pivot_inst.columns]
    x = range(len(dates))
    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = [0.0] * len(dates)
    for cat in cats:
        vals = pivot_inst[cat].values
        ax.bar(x, vals, bottom=bottom, label=cat, color=CAT_COLORS[cat], alpha=0.85)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, rotation=30)
    ax.set_ylabel('机构持有规模（亿元）')
    ax.set_title('固收加基金机构持有规模（半年截面）', fontsize=14)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '3.2_inst_size.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_inst_ratio_trend(holder_summary) -> 'Path':
    """机构占比中位数折线"""
    dates = HALF_YEAR_DATES
    pivot = (holder_summary
             .pivot_table(index='report_date', columns='category', values='inst_ratio_median', aggfunc='median')
             .reindex(dates))
    cats = [c for c in CAT_ORDER if c in pivot.columns]
    fig, ax = plt.subplots(figsize=(10, 5))
    for cat in cats:
        ax.plot(dates, pivot[cat], label=cat, color=CAT_COLORS[cat],
                marker='o', linewidth=2)
    ax.set_ylabel('机构持有占比中位数（%）')
    ax.set_title('固收加基金机构持有占比趋势', fontsize=14)
    ax.tick_params(axis='x', rotation=30)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '3.3_inst_ratio_trend.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_delta_bar(size_inc) -> 'Path':
    """25年规模增量 by 分类，机构 vs 散户拆解"""
    if size_inc.empty or 'category' not in size_inc.columns:
        return IMG_DIR / '3.4_delta_bar.png'
    grp = size_inc.dropna(subset=['category']).groupby('category').agg(
        delta_inst=('delta_inst', 'sum'),
        delta_total=('delta_total', 'sum'),
    ).reindex(CAT_ORDER).fillna(0)
    grp['delta_retail'] = grp['delta_total'] - grp['delta_inst']
    x = range(len(grp))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, grp['delta_inst'], label='机构增量', color='#4472C4', alpha=0.85)
    ax.bar(x, grp['delta_retail'], bottom=grp['delta_inst'], label='散户增量',
           color='#ED7D31', alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(grp.index)
    ax.axhline(0, color='gray', linewidth=0.5)
    ax.set_ylabel('规模增量（亿元）')
    ax.set_title('2024→2025 各分类规模增量（机构 vs 散户）', fontsize=13)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '3.4_delta_bar.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_size_vs_ret(size_inc) -> 'Path':
    """散点图：25 年规模增量 vs 24 年收益率"""
    if size_inc.empty or 'delta_total' not in size_inc.columns:
        return IMG_DIR / '3.5_size_vs_ret.png'
    df = size_inc.dropna(subset=['delta_total', 'ret_2024', 'category'])
    df = df[(df['delta_total'].abs() < 200) & (df['ret_2024'].abs() < 0.5)]
    fig, ax = plt.subplots(figsize=(8, 6))
    for cat in CAT_ORDER:
        sub = df[df['category'] == cat]
        ax.scatter(sub['ret_2024'] * 100, sub['delta_total'],
                   label=cat, color=CAT_COLORS[cat], alpha=0.5, s=20)
    ax.axhline(0, color='gray', linewidth=0.5)
    ax.axvline(0, color='gray', linewidth=0.5)
    ax.set_xlabel('2024 年收益率（%）')
    ax.set_ylabel('2024→2025 规模增量（亿元）')
    ax.set_title('规模增量 vs 24 年业绩（基金层面）', fontsize=13)
    ax.legend()
    plt.tight_layout()
    path = IMG_DIR / '3.5_size_vs_ret.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ── P0 新增图表 ────────────────────────────────────────────────────────────────

def plot_debt_fund_ratio(ratio_df) -> 'Path':
    """§1 固收加在债基中的规模占比（双轴：柱状+折线）"""
    path = IMG_DIR / '1.2_debt_fund_ratio.png'
    if ratio_df is None or ratio_df.empty:
        return path

    df = ratio_df.dropna(subset=['fi_plus_aum', 'pure_debt_aum']).copy()
    dates = df['report_date'].tolist()
    x = range(len(dates))

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(x, df['pure_debt_aum'], label='纯债型', color='#9DC3E6', alpha=0.85)
    ax1.bar(x, df['fi_plus_aum'], bottom=df['pure_debt_aum'],
            label='固收加', color='#2E75B6', alpha=0.85)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(dates, rotation=30)
    ax1.set_ylabel('规模（亿元）')
    ax1.legend(loc='upper left')

    ax2 = ax1.twinx()
    ax2.plot(list(x), df['fi_plus_ratio'], color='#E07B54',
             marker='o', linewidth=2, label='固收加占比（右轴）')
    ax2.set_ylabel('固收加占比（%）')
    ax2.set_ylim(0, 60)
    ax2.legend(loc='upper right')

    ax1.set_title('固收加在债基中的规模占比演变', fontsize=14)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_annual_mdd_trend(mdd_df) -> 'Path':
    """§5 各年度 MDD 中位数（分类分组柱状图）"""
    path = IMG_DIR / '5.1_annual_mdd_trend.png'
    if mdd_df is None or mdd_df.empty:
        return path

    years = ['2023', '2024', '2025']
    cats = [c for c in CAT_ORDER if c in mdd_df['category'].values]
    x = np.arange(len(years))
    width = 0.2
    fig, ax = plt.subplots(figsize=(10, 5))

    for i, cat in enumerate(cats):
        vals = []
        for yr in years:
            sub = mdd_df[(mdd_df['year'] == yr) & (mdd_df['category'] == cat)]['mdd']
            vals.append(sub.median() * 100 if not sub.empty else 0.0)
        ax.bar(x + i * width, vals, width, label=cat,
               color=CAT_COLORS[cat], alpha=0.85)

    ax.axhline(0, color='gray', linewidth=0.5)
    ax.set_xticks(x + width * (len(cats) - 1) / 2)
    ax.set_xticklabels(years)
    ax.set_ylabel('最大回撤中位数（%）')
    ax.set_title('固收加基金年度最大回撤中位数', fontsize=14)
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_ret_mdd_scatter(fund_perf, mdd_df) -> 'Path':
    """§5 收益-回撤散点图（每年一图，3 合 1）"""
    path = IMG_DIR / '5.2_ret_mdd_scatter.png'
    if mdd_df is None or mdd_df.empty or fund_perf is None or fund_perf.empty:
        return path

    years = ['2023', '2024', '2025']
    ret_cols = {'2023': 'ret_2023', '2024': 'ret_2024', '2025': 'ret_2025'}
    cats = [c for c in CAT_ORDER if c in fund_perf['category'].values]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
    for ax, yr in zip(axes, years):
        ret_col = ret_cols[yr]
        mdd_yr = mdd_df[mdd_df['year'] == yr][['c_fd_code', 'mdd']].copy()
        merged = fund_perf[['c_fd_code', 'category', ret_col]].merge(mdd_yr, on='c_fd_code')
        merged = merged.dropna(subset=[ret_col, 'mdd'])
        # 过滤极端值以便阅读
        merged = merged[merged[ret_col].abs() < 0.6]

        for cat in cats:
            sub = merged[merged['category'] == cat]
            ax.scatter(sub[ret_col] * 100, sub['mdd'] * 100,
                       label=cat, color=CAT_COLORS[cat], alpha=0.45, s=15)
        ax.axhline(0, color='gray', linewidth=0.4, linestyle='--')
        ax.axvline(0, color='gray', linewidth=0.4, linestyle='--')
        ax.set_xlabel('年度收益（%）')
        ax.set_ylabel('年度最大回撤（%）')
        ax.set_title(f'{yr}年', fontsize=12)
        ax.legend(fontsize=7)

    plt.suptitle('固收加基金收益-回撤分布', fontsize=14)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ── P1 新增图表 ────────────────────────────────────────────────────────────────

def plot_new_issuance(new_iss) -> 'Path':
    """§3 新发市场：按季度 × 分类的堆叠柱状图"""
    path = IMG_DIR / '3.6_new_issuance.png'
    if new_iss is None or new_iss.empty:
        return path

    quarters = sorted(new_iss['est_quarter'].unique())
    cats = [c for c in CAT_ORDER if c in new_iss['category'].values]
    pivot = (new_iss.pivot_table(index='est_quarter', columns='category',
                                 values='count', aggfunc='sum')
             .reindex(quarters).fillna(0))
    x = range(len(quarters))
    fig, ax = plt.subplots(figsize=(12, 5))
    bottom = np.zeros(len(quarters))
    for cat in cats:
        if cat not in pivot.columns:
            continue
        vals = pivot[cat].values
        ax.bar(x, vals, bottom=bottom, label=cat, color=CAT_COLORS[cat], alpha=0.85)
        bottom = bottom + vals

    ax.set_xticks(list(x))
    ax.set_xticklabels(quarters, rotation=45)
    ax.set_ylabel('新发基金数量（只）')
    ax.set_title('固收加基金新发市场（2023-2025，按季度）', fontsize=14)
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_asset_allocation(asset_alloc) -> 'Path':
    """§4.1 大类资产配置中位数（堆叠柱状图，5个半年截面）"""
    path = IMG_DIR / '4.1_asset_allocation.png'
    if asset_alloc is None or asset_alloc.empty:
        return path

    dates = HALF_YEAR_DATES
    summary = (asset_alloc.groupby('report_date')[
        ['stk_ratio', 'cb_ratio', 'pure_bd_ratio', 'cash_ratio']
    ].median().reindex(dates).fillna(0))

    x = range(len(dates))
    components = [
        ('stk_ratio',      '股票',   '#ED7D31'),
        ('cb_ratio',       '可转债', '#FFC000'),
        ('pure_bd_ratio',  '纯债',   '#5B9BD5'),
        ('cash_ratio',     '现金',   '#A9D18E'),
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = np.zeros(len(dates))
    for col, label, color in components:
        vals = summary[col].values
        ax.bar(x, vals, bottom=bottom, label=label, color=color, alpha=0.88)
        bottom = bottom + vals

    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, rotation=30)
    ax.set_ylabel('占净值比例中位数（%）')
    ax.set_title('固收加基金大类资产配置走势（整体中位数）', fontsize=14)
    ax.legend(loc='lower right')
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_sector_allocation(sector_alloc) -> 'Path':
    """§4.4 最新季报重仓股行业配置（等权均值，水平柱状图）"""
    path = IMG_DIR / '4.4_sector_allocation.png'
    if sector_alloc is None or sector_alloc.empty:
        return path

    # 使用最新两个季度对比
    latest_dates = sorted(sector_alloc['report_date'].unique())[-2:]
    fig, axes = plt.subplots(1, len(latest_dates), figsize=(14, 7))
    if len(latest_dates) == 1:
        axes = [axes]

    for ax, rd in zip(axes, latest_dates):
        sub = sector_alloc[sector_alloc['report_date'] == rd].copy()
        # 先按基金汇总行业权重，再对基金取均值
        ind_wt = (sub.groupby(['c_fd_code', 'ind_l1_name'])['ind_nav_ratio']
                  .sum().reset_index()
                  .groupby('ind_l1_name')['ind_nav_ratio']
                  .mean().sort_values(ascending=True))
        top = ind_wt.tail(15)
        ax.barh(top.index, top.values, color='#4472C4', alpha=0.82)
        ax.set_xlabel('平均持仓权重（%）')
        ax.set_title(f'{rd}\n重仓股行业（等权均值）', fontsize=11)
        ax.tick_params(axis='y', labelsize=9)

    plt.suptitle('固收加基金重仓股行业配置', fontsize=14)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

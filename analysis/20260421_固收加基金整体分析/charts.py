"""
固收加基金整体分析 — 图表模块
接收 analyze.py 传入的 DataFrame，输出 PNG 到 images/
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

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

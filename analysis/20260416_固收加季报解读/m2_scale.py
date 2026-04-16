"""
模块二：规模变化

输出 data/m2_scale.xlsx
  Sheet1: 基金清单（核心基础表）
  Sheet2: 分品类汇总
  Sheet3: 基金公司 TOP20
  Sheet4: 规模增长 TOP20
  Sheet5: 新发产品（本季成立）
  Sheet6: 历史趋势（各报告期总规模+数量）
  Sheet7: 按策略分类规模（c_eq_risk_level + c_stk_cb_strategy）
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.db_connector import DorisConnector
from utils.log import setup_logger
from config import (
    REPORT_DATE, PREV_DATE, HIST_DATES, MANUAL_DIR,
    fetch_fi_universe, save_excel, date_to_style,
)

logger = setup_logger(__name__)
ENV = 'dev'


# ── 数据获取 ──────────────────────────────────────────────────────


def _fetch_nav(doris: DorisConnector, report_date: str) -> pd.DataFrame:
    """查询指定报告期的基金净值总额（主代码，季报口径）"""
    sql = """
    SELECT c_fd_code,
           c_fund_nav_total
    FROM tb_fd_asset_allocation
    WHERE c_report_date = :report_date
      AND c_style       = :style
      AND c_is_stat     = -1
    """
    return doris.query(sql, report_date=report_date, style=date_to_style(report_date))


def _fetch_tag_fi(doris: DorisConnector) -> pd.DataFrame:
    """查询固收+资产配置标签（当期）"""
    sql = """
    SELECT c_fd_code, c_eq_risk_level, c_stk_cb_strategy
    FROM tb_fd_tag_asset_fi
    WHERE c_report_date = :report_date
    """
    return doris.query(sql, report_date=REPORT_DATE)


def _fetch_hist_scale(doris: DorisConnector, universe_codes: list[str]) -> pd.DataFrame:
    """查询所有 HIST_DATES 的规模，用于历史趋势"""
    sql = """
    SELECT c_fd_code, c_report_date, c_fund_nav_total
    FROM tb_fd_asset_allocation
    WHERE c_report_date >= :start_date
      AND c_report_date <= :end_date
      AND c_style IN ('01', '03', '05', '06')
      AND c_is_stat = -1
    """
    df = doris.query(sql, start_date=HIST_DATES[0], end_date=HIST_DATES[-1])
    # 只保留 HIST_DATES 中的日期（排除非标准报告期）
    valid_dates = set(HIST_DATES)
    df = df[df['c_report_date'].astype(str).isin(valid_dates)]
    # 只保留宇宙基金
    df = df[df['c_fd_code'].isin(universe_codes)]
    return df


# ── 组装 Sheet ────────────────────────────────────────────────────


def _build_fund_list(universe: pd.DataFrame,
                     nav_cur: pd.DataFrame,
                     nav_prev: pd.DataFrame,
                     tag: pd.DataFrame) -> pd.DataFrame:
    df = universe.copy()

    nav_cur  = nav_cur.rename(columns={'c_fund_nav_total': '本期规模(亿)'})
    nav_prev = nav_prev.rename(columns={'c_fund_nav_total': '上期规模(亿)'})

    df = df.merge(nav_cur[['c_fd_code', '本期规模(亿)']], on='c_fd_code', how='left')
    df = df.merge(nav_prev[['c_fd_code', '上期规模(亿)']], on='c_fd_code', how='left')
    df = df.merge(tag[['c_fd_code', 'c_eq_risk_level', 'c_stk_cb_strategy']],
                  on='c_fd_code', how='left')

    # 规模单位：元 → 亿
    df['本期规模(亿)'] = (df['本期规模(亿)'] / 1e8).round(4)
    df['上期规模(亿)'] = (df['上期规模(亿)'] / 1e8).round(4)
    df['规模变化(亿)'] = (df['本期规模(亿)'] - df['上期规模(亿)']).round(4)
    df['规模变化%']   = (
        (df['本期规模(亿)'] / df['上期规模(亿)'] - 1) * 100
    ).round(2)

    # 是否新成立（本季内）
    df['c_estabdate'] = pd.to_datetime(df['c_estabdate'])
    df['是否新成立'] = df['c_estabdate'].apply(
        lambda d: '是' if pd.notna(d) and str(d.date()) > PREV_DATE else '否'
    )

    return df[[
        'c_fd_code', 'c_short_name', 'c_type2_name', 'c_company_name', 'c_mgr_name',
        'c_estabdate', '本期规模(亿)', '上期规模(亿)', '规模变化(亿)', '规模变化%',
        'c_eq_risk_level', 'c_stk_cb_strategy', '是否新成立',
    ]].rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型', 'c_company_name': '基金公司',
        'c_mgr_name': '基金经理', 'c_estabdate': '成立日期',
        'c_eq_risk_level': '风险特征', 'c_stk_cb_strategy': '股债策略',
    })


def _build_category_summary(fund_list: pd.DataFrame) -> pd.DataFrame:
    grp = fund_list.groupby('二级类型').agg(
        数量=('基金代码', 'count'),
        本期规模合计=('本期规模(亿)', 'sum'),
        上期规模合计=('上期规模(亿)', 'sum'),
    ).reset_index()
    grp['规模环比%'] = ((grp['本期规模合计'] / grp['上期规模合计'] - 1) * 100).round(2)
    grp['本期规模合计'] = grp['本期规模合计'].round(2)
    grp['上期规模合计'] = grp['上期规模合计'].round(2)
    total = pd.DataFrame([{
        '二级类型': '合计',
        '数量': grp['数量'].sum(),
        '本期规模合计': grp['本期规模合计'].sum().round(2),
        '上期规模合计': grp['上期规模合计'].sum().round(2),
        '规模环比%': None,
    }])
    return pd.concat([grp.sort_values('本期规模合计', ascending=False), total],
                     ignore_index=True)


def _build_company_top20(fund_list: pd.DataFrame) -> pd.DataFrame:
    grp = fund_list.groupby('基金公司').agg(
        基金数量=('基金代码', 'count'),
        管理规模=('本期规模(亿)', 'sum'),
    ).reset_index().sort_values('管理规模', ascending=False).head(20)
    total = grp['管理规模'].sum()
    grp['市占率%'] = (grp['管理规模'] / total * 100).round(2)
    grp['管理规模'] = grp['管理规模'].round(2)
    grp.insert(0, '排名', range(1, len(grp) + 1))
    return grp.reset_index(drop=True)


def _build_hist_trend(hist_df: pd.DataFrame, universe_set: set) -> pd.DataFrame:
    hist_df = hist_df[hist_df['c_fd_code'].isin(universe_set)].copy()
    hist_df['c_fund_nav_total'] = hist_df['c_fund_nav_total'] / 1e8

    trend = hist_df.groupby('c_report_date').agg(
        总规模_亿=('c_fund_nav_total', 'sum'),
        基金数量=('c_fd_code', 'count'),
    ).reset_index().rename(columns={'c_report_date': '报告期'})
    trend['总规模_亿'] = trend['总规模_亿'].round(2)
    trend = trend.sort_values('报告期')
    return trend


def _build_strategy_summary(fund_list: pd.DataFrame) -> pd.DataFrame:
    """按 c_eq_risk_level × c_stk_cb_strategy 交叉汇总"""
    grp = fund_list.groupby(
        ['风险特征', '股债策略'], dropna=False
    ).agg(
        基金数量=('基金代码', 'count'),
        规模合计=('本期规模(亿)', 'sum'),
    ).reset_index()
    grp['规模合计'] = grp['规模合计'].round(2)
    grp['风险特征'] = grp['风险特征'].fillna('未标注')
    grp['股债策略'] = grp['股债策略'].fillna('未标注')
    return grp.sort_values('规模合计', ascending=False).reset_index(drop=True)


# ── 主流程 ────────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        logger.info("=== 模块二：规模变化 ===")

        universe = fetch_fi_universe(doris, REPORT_DATE)
        nav_cur  = _fetch_nav(doris, REPORT_DATE)
        nav_prev = _fetch_nav(doris, PREV_DATE)
        tag      = _fetch_tag_fi(doris)

        universe_codes = universe['c_fd_code'].tolist()
        hist_df  = _fetch_hist_scale(doris, universe_codes)

    fund_list = _build_fund_list(universe, nav_cur, nav_prev, tag)
    logger.info(f"基金清单行数：{len(fund_list)}")

    sheet1 = fund_list
    sheet2 = _build_category_summary(fund_list)
    sheet3 = _build_company_top20(fund_list)
    sheet4 = (
        fund_list[fund_list['是否新成立'] == '否']
        .sort_values('规模变化(亿)', ascending=False)
        .head(20)
        .reset_index(drop=True)
    )
    sheet4.insert(0, '排名', range(1, len(sheet4) + 1))

    # Sheet5: 新发产品
    new_funds = fund_list[fund_list['是否新成立'] == '是'].copy()
    # 尝试合并 manual_data/new_funds.xlsx（用户补充份额数据）
    manual_path = MANUAL_DIR / 'new_funds.xlsx'
    if manual_path.exists():
        manual_df = pd.read_excel(manual_path)
        if '基金代码' in manual_df.columns and '新发份额(亿份)' in manual_df.columns:
            new_funds = new_funds.merge(
                manual_df[['基金代码', '新发份额(亿份)']], on='基金代码', how='left'
            )
    else:
        new_funds['新发份额(亿份)'] = None  # 留空待填

    sheet5 = new_funds.reset_index(drop=True)

    sheet6 = _build_hist_trend(hist_df, set(universe_codes))
    sheet7 = _build_strategy_summary(fund_list)

    save_excel({
        '基金清单':       sheet1,
        '分品类汇总':     sheet2,
        '基金公司TOP20':  sheet3,
        '规模增长TOP20':  sheet4,
        '新发产品':       sheet5,
        '历史趋势':       sheet6,
        '策略分类规模':   sheet7,
    }, 'm2_scale.xlsx')
    logger.info("模块二完成")


if __name__ == '__main__':
    run()

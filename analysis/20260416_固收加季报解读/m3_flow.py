"""
模块三：资金流向（估算）

公式：净申购(亿) ≈ 期末规模 - 期初规模 × (1 + 近3月收益率/100)
收益率来源：tb_fd_perform_abs（c_period_code='01'，取 PERF_DATE）

注意：
- 排除本季新成立基金（无上期规模）
- 报告中标注"估算值，误差来源：分红/拆分/近3月≠精确季度"

输出 data/m3_flow.xlsx
  Sheet1: 每只基金净申购估算
  Sheet2: 分品类汇总
  Sheet3: 基金公司净申购 TOP10
  Sheet4: 净申购 TOP20 产品
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.db_connector import DorisConnector
from utils.log import setup_logger
from config import (
    REPORT_DATE, PREV_DATE, PERF_DATE,
    fetch_fi_universe, save_excel, date_to_style,
)

logger = setup_logger(__name__)
ENV = 'dev'


# ── 数据获取 ──────────────────────────────────────────────────────


def _fetch_nav(doris: DorisConnector, report_date: str) -> pd.DataFrame:
    sql = """
    SELECT c_fd_code, c_fund_nav_total
    FROM tb_fd_asset_allocation
    WHERE c_report_date = :report_date
      AND c_style       = :style
      AND c_is_stat     = -1
    """
    return doris.query(sql, report_date=report_date, style=date_to_style(report_date))


def _fetch_perf_q(doris: DorisConnector, fd_codes: list[str]) -> pd.DataFrame:
    """近3月收益率（period_code='01'）"""
    sql = """
    SELECT c_fd_code, c_period_ret
    FROM tb_fd_perform_abs
    WHERE c_trade_date  = :perf_date
      AND c_period_code = '01'
      AND c_fd_code IN (:code_list)
    """
    return doris.query_batch(sql, fd_codes, perf_date=PERF_DATE)


# ── 估算 & 组装 ───────────────────────────────────────────────────


def _build_fund_flow(universe: pd.DataFrame,
                     nav_cur: pd.DataFrame,
                     nav_prev: pd.DataFrame,
                     perf_q: pd.DataFrame) -> pd.DataFrame:
    df = universe[['c_fd_code', 'c_short_name', 'c_type2_name',
                   'c_company_name', 'c_estabdate']].copy()

    nav_cur  = nav_cur.rename(columns={'c_fund_nav_total': '期末规模_元'})
    nav_prev = nav_prev.rename(columns={'c_fund_nav_total': '期初规模_元'})
    perf_q   = perf_q.rename(columns={'c_period_ret': '近3月收益率%'})

    df = df.merge(nav_cur, on='c_fd_code', how='left')
    df = df.merge(nav_prev, on='c_fd_code', how='left')
    df = df.merge(perf_q, on='c_fd_code', how='left')

    # 期末/期初规模转换为亿
    df['期末规模(亿)'] = (df['期末规模_元'] / 1e8).round(4)
    df['期初规模(亿)'] = (df['期初规模_元'] / 1e8).round(4)

    # 排除本季新成立（无期初规模）
    df['c_estabdate'] = pd.to_datetime(df['c_estabdate'])
    is_new = df['c_estabdate'].apply(lambda d: pd.notna(d) and str(d.date()) > PREV_DATE)

    # 估算净申购
    def calc_flow(row):
        if is_new[row.name]:
            return None  # 新基金排除
        if pd.isna(row['期初规模(亿)']) or pd.isna(row['期末规模(亿)']):
            return None
        ret = row['近3月收益率%'] if pd.notna(row['近3月收益率%']) else 0.0
        return round(row['期末规模(亿)'] - row['期初规模(亿)'] * (1 + ret / 100), 4)

    df['估算净申购(亿)'] = df.apply(calc_flow, axis=1)

    # 数据备注
    def data_note(row):
        if is_new[row.name]:
            return '新成立基金，排除'
        if pd.isna(row['近3月收益率%']):
            return '收益率缺失，默认0%估算'
        return '正常估算'

    df['数据备注'] = df.apply(data_note, axis=1)

    return df[[
        'c_fd_code', 'c_short_name', 'c_type2_name', 'c_company_name',
        '期初规模(亿)', '期末规模(亿)', '近3月收益率%', '估算净申购(亿)', '数据备注',
    ]].rename(columns={
        'c_fd_code': '基金代码', 'c_short_name': '基金简称',
        'c_type2_name': '二级类型', 'c_company_name': '基金公司',
    })


def _build_category_flow(fund_flow: pd.DataFrame) -> pd.DataFrame:
    sub = fund_flow[fund_flow['数据备注'] != '新成立基金，排除'].copy()
    grp = sub.groupby('二级类型').agg(
        基金数量=('基金代码', 'count'),
        净申购合计_亿=('估算净申购(亿)', 'sum'),
        期末规模合计_亿=('期末规模(亿)', 'sum'),
    ).reset_index()
    grp['净申购合计_亿']   = grp['净申购合计_亿'].round(2)
    grp['期末规模合计_亿'] = grp['期末规模合计_亿'].round(2)
    total = pd.DataFrame([{
        '二级类型': '合计',
        '基金数量': grp['基金数量'].sum(),
        '净申购合计_亿': grp['净申购合计_亿'].sum().round(2),
        '期末规模合计_亿': grp['期末规模合计_亿'].sum().round(2),
    }])
    return pd.concat([grp.sort_values('净申购合计_亿', ascending=False), total],
                     ignore_index=True)


def _build_company_top10(fund_flow: pd.DataFrame) -> pd.DataFrame:
    sub = fund_flow[fund_flow['数据备注'] != '新成立基金，排除']
    grp = (
        sub.groupby('基金公司')['估算净申购(亿)']
        .sum()
        .nlargest(10)
        .reset_index()
    )
    grp['估算净申购(亿)'] = grp['估算净申购(亿)'].round(2)
    grp.insert(0, '排名', range(1, len(grp) + 1))
    return grp


def _build_top20_fund(fund_flow: pd.DataFrame) -> pd.DataFrame:
    sub = fund_flow[fund_flow['数据备注'] != '新成立基金，排除']
    top20 = sub.nlargest(20, '估算净申购(亿)').copy()
    top20.insert(0, '排名', range(1, len(top20) + 1))
    return top20.reset_index(drop=True)


# ── 主流程 ────────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        logger.info("=== 模块三：资金流向 ===")

        universe = fetch_fi_universe(doris, REPORT_DATE)
        fd_codes = universe['c_fd_code'].tolist()

        nav_cur  = _fetch_nav(doris, REPORT_DATE)
        nav_prev = _fetch_nav(doris, PREV_DATE)
        perf_q   = _fetch_perf_q(doris, fd_codes)

    fund_flow = _build_fund_flow(universe, nav_cur, nav_prev, perf_q)
    valid_cnt = fund_flow[fund_flow['数据备注'] != '新成立基金，排除']['基金代码'].count()
    logger.info(f"参与估算基金数：{valid_cnt}")

    save_excel({
        '每只基金净申购估算': fund_flow,
        '分品类汇总':        _build_category_flow(fund_flow),
        '基金公司净申购TOP10': _build_company_top10(fund_flow),
        '净申购TOP20产品':   _build_top20_fund(fund_flow),
    }, 'm3_flow.xlsx')
    logger.info("模块三完成")


if __name__ == '__main__':
    run()

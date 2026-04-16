"""
模块一：市场环境

输出 data/m1_market.xlsx
  Sheet1: 主要指数行情（当季 / YTD 涨跌幅）
  Sheet2: 转债估值（转股溢价率中位数 + 历史分位数）
  Sheet3: 利率与信用利差（读 manual_data/interest_rate.csv，文件不存在则跳过）
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.db_connector import DorisConnector
from utils.log import setup_logger
from config import (
    REPORT_DATE, PREV_DATE, YEAR_START, OUTPUT_DIR, MANUAL_DIR,
    save_excel,
)

logger = setup_logger(__name__)
ENV = 'dev'

# 指数代码 → 中文名称
INDEX_MAP = {
    '000300': '沪深300',
    '000905': '中证500',
    '399006': '创业板指',
    'HKHSI':  '恒生指数',
    '000832': '中证转债',
    'CBA00101': '中债综合财富',
}


# ── 数据获取 ──────────────────────────────────────────────────────


def _fetch_index_prices(doris: DorisConnector) -> pd.DataFrame:
    """查询各指数在 YEAR_START、PREV_DATE、REPORT_DATE 附近的收盘价"""
    codes = list(INDEX_MAP.keys())
    placeholders = ', '.join([f':c{i}' for i in range(len(codes))])
    sql = f"""
    SELECT c_trade_date, c_idx_code, c_close
    FROM tb_idx_quote_daily
    WHERE c_idx_code IN ({placeholders})
      AND c_trade_date >= :year_start
      AND c_trade_date <= :report_date
    ORDER BY c_idx_code, c_trade_date
    """
    params = {f'c{i}': code for i, code in enumerate(codes)}
    params.update(year_start=YEAR_START, report_date=REPORT_DATE)

    with doris.engine.connect() as conn:
        from sqlalchemy import text
        df = pd.read_sql(text(sql), conn, params=params)
    # 统一转为 datetime64，避免与字符串比较时类型不匹配
    df['c_trade_date'] = pd.to_datetime(df['c_trade_date'])
    return df


def _build_index_sheet(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    对每只指数取三个价格节点：
      - ytd_open : >= YEAR_START 的第一个交易日
      - qtr_open : <= PREV_DATE 最后一个交易日
      - qtr_close: <= REPORT_DATE 最后一个交易日（通常就是 REPORT_DATE）
    """
    rows = []
    for code, name in INDEX_MAP.items():
        sub = price_df[price_df['c_idx_code'] == code].sort_values('c_trade_date')
        if sub.empty:
            logger.warning(f"指数 {code}({name}) 无行情数据，跳过")
            continue

        # YTD 起始：>= YEAR_START 的最早一条
        ytd_sub = sub[sub['c_trade_date'] >= pd.Timestamp(YEAR_START)]
        ytd_open = ytd_sub.iloc[0]['c_close'] if not ytd_sub.empty else None

        # 当季起始：<= PREV_DATE 的最后一条
        qtr_open_sub = sub[sub['c_trade_date'] <= pd.Timestamp(PREV_DATE)]
        qtr_open = qtr_open_sub.iloc[-1]['c_close'] if not qtr_open_sub.empty else None

        # 当季末：<= REPORT_DATE 的最后一条
        qtr_close_sub = sub[sub['c_trade_date'] <= pd.Timestamp(REPORT_DATE)]
        qtr_close = qtr_close_sub.iloc[-1]['c_close'] if not qtr_close_sub.empty else None

        def pct(end, start):
            if end is None or start is None or start == 0:
                return None
            return round((end / start - 1) * 100, 2)

        rows.append({
            '指数名称':    name,
            '指数代码':    code,
            '期初点位':    round(qtr_open, 2) if qtr_open else None,
            '期末点位':    round(qtr_close, 2) if qtr_close else None,
            '当季涨跌幅%': pct(qtr_close, qtr_open),
            'YTD涨跌幅%':  pct(qtr_close, ytd_open),
        })
    return pd.DataFrame(rows)


def _fetch_cb_prem(doris: DorisConnector) -> pd.DataFrame:
    """查询 PREV_DATE 和 REPORT_DATE 的转股溢价率，以及近5年历史分位计算用数据"""
    sql = """
    SELECT c_trade_date, c_conv_prem_rate
    FROM tb_cb_analysis
    WHERE c_trade_date >= '2020-01-01'
      AND c_trade_date <= :report_date
      AND c_conv_prem_rate IS NOT NULL
    ORDER BY c_trade_date
    """
    df = doris.query(sql, report_date=REPORT_DATE)
    df['c_trade_date'] = pd.to_datetime(df['c_trade_date'])
    return df


def _build_cb_sheet(cb_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算两个报告期的转股溢价率中位数，以及期末在历史（2020年以来）的分位数
    """
    rows = []
    for label, dt in [('上期（' + PREV_DATE + '）', pd.Timestamp(PREV_DATE)),
                      ('本期（' + REPORT_DATE + '）', pd.Timestamp(REPORT_DATE))]:
        day_df = cb_df[cb_df['c_trade_date'] == dt]
        if day_df.empty:
            # 取最近一个有数据的交易日
            avail = cb_df[cb_df['c_trade_date'] <= dt]
            if avail.empty:
                rows.append({'报告期': label, '转股溢价率中位数%': None, '历史分位（2020至今）': None})
                continue
            latest_date = avail['c_trade_date'].max()
            day_df = avail[avail['c_trade_date'] == latest_date]

        median_val = day_df['c_conv_prem_rate'].median()

        # 历史分位：以每日中位数序列计算
        daily_median = cb_df.groupby('c_trade_date')['c_conv_prem_rate'].median()
        pctrank = (daily_median < median_val).sum() / len(daily_median)

        rows.append({
            '报告期':             label,
            '转股溢价率中位数%':   round(median_val, 2),
            '历史分位（2020至今）': f'{round(pctrank * 100, 1)}%',
        })
    return pd.DataFrame(rows)


def _read_interest_rate_csv() -> pd.DataFrame | None:
    """读取手动放置的利率/信用利差 CSV，不存在则返回 None"""
    csv_path = MANUAL_DIR / 'interest_rate.csv'
    if not csv_path.exists():
        logger.info("interest_rate.csv 不存在，跳过 Sheet3")
        return None
    df = pd.read_csv(csv_path)
    # 转为宽表：行=指标, 列=日期
    pivot = df.pivot(index='indicator', columns='date', values='value').reset_index()
    pivot.rename(columns={'indicator': '指标'}, inplace=True)
    return pivot


# ── 主流程 ────────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        logger.info("=== 模块一：市场环境 ===")

        price_df = _fetch_index_prices(doris)
        cb_df    = _fetch_cb_prem(doris)

    sheet1 = _build_index_sheet(price_df)
    sheet2 = _build_cb_sheet(cb_df)
    sheet3 = _read_interest_rate_csv()

    sheets = {
        '指数行情':     sheet1,
        '转债估值':     sheet2,
    }
    if sheet3 is not None:
        sheets['利率与信用利差'] = sheet3

    save_excel(sheets, 'm1_market.xlsx')
    logger.info("模块一完成")


if __name__ == '__main__':
    run()

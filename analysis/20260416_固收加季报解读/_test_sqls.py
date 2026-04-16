"""
SQL 验证脚本：对所有模块的查询逐一执行 LIMIT 5，验证列名和返回数据。
运行：python analysis/20260416_固收加季报解读/_test_sqls.py
"""
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 跳过 oracledb.init_oracle_client()（测试只用 Doris，不需要 Oracle 客户端）
import unittest.mock as mock
import oracledb
with mock.patch.object(oracledb, 'init_oracle_client', return_value=None):
    from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

REPORT_DATE = '2025-12-31'
PREV_DATE   = '2025-09-30'
PERF_DATE   = '2026-04-15'
STYLE_CUR   = '06'   # date_to_style('2025-12-31')
STYLE_PREV  = '03'   # date_to_style('2025-09-30')

SQLS = {
    # ── config: fetch_fi_universe ──────────────────────────────────
    'config.fetch_fi_universe': ("""
        SELECT
            b.c_fd_code,
            b.c_short_name,
            cat.c_type2_code,
            cat.c_type2_name,
            b.c_company_name,
            b.c_manager_name,
            b.c_estabdate
        FROM tb_fd_category cat
        JOIN tb_fd_basic_info b ON b.c_fd_code = cat.c_fd_code
        WHERE cat.c_report_date = :report_date
          AND cat.c_type1_code  = '002'
          AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
        ORDER BY b.c_fd_code
        LIMIT 5
    """, {'report_date': REPORT_DATE}),

    # ── m1: index prices ──────────────────────────────────────────
    'm1.index_prices': ("""
        SELECT c_trade_date, c_idx_code, c_close
        FROM tb_idx_quote_daily
        WHERE c_idx_code IN ('000300', '000905', '399006', '000832')
          AND c_trade_date = :report_date
        LIMIT 5
    """, {'report_date': REPORT_DATE}),

    'm1.cb_prem': ("""
        SELECT c_trade_date, c_conv_prem_rate
        FROM tb_cb_analysis
        WHERE c_trade_date = :report_date
          AND c_conv_prem_rate IS NOT NULL
        LIMIT 5
    """, {'report_date': REPORT_DATE}),

    # ── m2: nav ───────────────────────────────────────────────────
    'm2.nav_cur': ("""
        SELECT c_fd_code, c_fund_nav_total
        FROM tb_fd_asset_allocation
        WHERE c_report_date = :report_date
          AND c_style       = :style
          AND c_is_stat     = -1
        LIMIT 5
    """, {'report_date': REPORT_DATE, 'style': STYLE_CUR}),

    'm2.tag_fi': ("""
        SELECT c_fd_code, c_eq_risk_level, c_stk_cb_strategy
        FROM tb_fd_tag_asset_fi
        WHERE c_report_date = :report_date
        LIMIT 5
    """, {'report_date': REPORT_DATE}),

    'm2.hist_scale': ("""
        SELECT c_fd_code, c_report_date, c_fund_nav_total
        FROM tb_fd_asset_allocation
        WHERE c_report_date >= '2020-03-31'
          AND c_report_date <= :report_date
          AND c_style IN ('01', '03', '05', '06')
          AND c_is_stat = -1
        LIMIT 5
    """, {'report_date': REPORT_DATE}),

    # ── m3: perf_q ────────────────────────────────────────────────
    'm3.perf_q': ("""
        SELECT c_fd_code, c_period_ret
        FROM tb_fd_perform_abs
        WHERE c_trade_date  = :perf_date
          AND c_period_code = '01'
        LIMIT 5
    """, {'perf_date': PERF_DATE}),

    # ── m4: perf ─────────────────────────────────────────────────
    'm4.perf': ("""
        SELECT c_fd_code, c_period_code, c_period_ret, c_mdd, c_sharpe, c_sortino
        FROM tb_fd_perform_abs
        WHERE c_trade_date  = :perf_date
          AND c_period_code IN ('01', '07')
        LIMIT 5
    """, {'perf_date': PERF_DATE}),

    # ── m5: asset_alloc ──────────────────────────────────────────
    'm5.asset_alloc': ("""
        SELECT c_fd_code,
               c_stk_total_ratio,
               c_bd_convertible_ratio,
               c_stk_equity_ratio,
               c_stk_hk_connect_ratio
        FROM tb_fd_asset_allocation
        WHERE c_report_date = :report_date
          AND c_style       = :style
          AND c_is_stat     = -1
        LIMIT 5
    """, {'report_date': REPORT_DATE, 'style': STYLE_CUR}),

    # ── m5: stk holdings ─────────────────────────────────────────
    'm5.stk_holdings': ("""
        SELECT p.c_fd_code, p.c_stk_code, p.c_hold_value, p.c_nav_ratio,
               b.c_stk_name,
               d.c_param_name AS c_industry
        FROM tb_fd_portfolio_stk p
        LEFT JOIN tb_stk_basic_info b ON b.c_stk_code = p.c_stk_code
        LEFT JOIN tb_stk_industry si
               ON si.c_stk_code  = p.c_stk_code
              AND si.c_trade_date = :report_date
        LEFT JOIN tb_dict_params d
               ON d.c_param_code = LEFT(si.c_citic_code, 6)
              AND d.c_param_type = '中信行业分类'
        WHERE p.c_report_date = :report_date
          AND p.c_style       = :style
          AND p.c_is_stat     = -1
        LIMIT 5
    """, {'report_date': REPORT_DATE, 'style': STYLE_CUR}),

    # ── m5: cb holdings ──────────────────────────────────────────
    'm5.cb_holdings': ("""
        SELECT p.c_fd_code, p.c_bd_code, p.c_bd_name,
               p.c_bd_type, p.c_hold_value, p.c_nav_ratio,
               bb.c_credit_rating,
               bb.c_stk_code AS c_stk_code,
               d.c_param_name AS c_stk_industry
        FROM tb_fd_portfolio_bd p
        LEFT JOIN tb_bd_basic_info bb
               ON bb.c_bd_code = p.c_bd_code
              AND bb.c_bd_type IN ('可转换债券', '可交换债券', '可分离交易可转债')
        LEFT JOIN tb_stk_industry si
               ON si.c_stk_code  = bb.c_stk_code
              AND si.c_trade_date = :report_date
        LEFT JOIN tb_dict_params d
               ON d.c_param_code = LEFT(si.c_citic_code, 6)
              AND d.c_param_type = '中信行业分类'
        WHERE p.c_report_date = :report_date
          AND p.c_style       = :style
          AND p.c_is_stat     = -1
        LIMIT 5
    """, {'report_date': REPORT_DATE, 'style': STYLE_CUR}),

    # ── m5: bd_style ─────────────────────────────────────────────
    'm5.bd_style': ("""
        SELECT c_fd_code,
               c_bd_type_style, c_bd_type_timing,
               c_leverage_pref, c_leverage_timing,
               c_credit_pref, c_credit_timing,
               c_duration_pref, c_duration_timing,
               c_leverage_avg, c_duration_avg
        FROM tb_fd_tag_bd_style
        WHERE c_report_date = :report_date
        LIMIT 5
    """, {'report_date': REPORT_DATE}),
}


def run():
    passed, failed = [], []

    with DorisConnector(ENV) as doris:
        with doris.engine.connect() as conn:
            for name, (sql, params) in SQLS.items():
                try:
                    import pandas as pd
                    df = pd.read_sql(text(sql), conn, params=params)
                    if df.empty:
                        logger.warning(f"[EMPTY] {name}  (0行，请确认数据是否存在)")
                        failed.append((name, 'empty result'))
                    else:
                        logger.info(f"[OK]    {name}  → {len(df)}行，列: {df.columns.tolist()}")
                        passed.append(name)
                except Exception as e:
                    logger.error(f"[FAIL]  {name}  → {e}")
                    failed.append((name, str(e)))

    print(f"\n{'='*60}")
    print(f"通过: {len(passed)}  失败/空: {len(failed)}")
    if failed:
        print("\n失败明细：")
        for name, err in failed:
            print(f"  {name}: {err}")


if __name__ == '__main__':
    run()

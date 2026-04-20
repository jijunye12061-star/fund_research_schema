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

import logging
import pandas as pd
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates

from utils.log import setup_logger
logger = setup_logger(__name__)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"  # 调度注入db_env参数；本地默认dev

OUTPUT_COLS = [
    'c_report_date', 'c_company_code', 'c_stk_code',
    'c_total_hold_mv', 'c_crowd_score',
]


# ==================== 数据查询 ====================

def _get_equity_funds(doris: DorisConnector, report_date: str) -> list[str]:
    """主动权益(001001) + 全部混合型(004)，仅主代码（去重A/C份额、联接基金）"""
    sql = """
    SELECT DISTINCT c.c_fd_code
    FROM tytdata.tb_fd_category c
    JOIN tytdata.tb_fd_basic_info b ON c.c_fd_code = b.c_fd_code
    WHERE (c.c_type2_code = '001001' OR c.c_type1_code = '004')
      AND c.c_report_date = :report_date
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    """
    return doris.query(sql, report_date=report_date)['c_fd_code'].tolist()


def _get_fund_company_map(doris: DorisConnector, fund_codes: list[str]) -> pd.DataFrame:
    """获取基金→公司代码映射（仅含有公司代码的基金）"""
    sql = """
    SELECT DISTINCT c_fd_code, c_company_code
    FROM tytdata.tb_fd_basic_info
    WHERE c_fd_code IN (:code_list)
      AND c_company_code IS NOT NULL
    """
    return doris.query_batch(sql, code_list=fund_codes)


def _query_full_holdings(doris: DorisConnector, fund_codes: list[str],
                         report_date: str) -> pd.DataFrame:
    """查询全持仓（半年报 c_style IN ('02','04')），去重后取最大市值"""
    sql = """
    SELECT c_fd_code, c_stk_code, MAX(c_hold_value) AS c_hold_value
    FROM tytdata.tb_fd_portfolio_stk
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style IN ('02', '04')
      AND c_hold_value > 0
      AND LENGTH(c_stk_code) = 6
    GROUP BY c_fd_code, c_stk_code
    """
    return doris.query_batch(sql, code_list=fund_codes, report_date=report_date)


# ==================== 计算 ====================

def _rank_by_mv(holdings: pd.DataFrame, company_code: str) -> pd.DataFrame:
    """按持仓市值合计做百分位排名，返回带 c_company_code 的结果"""
    agg = (holdings.groupby('c_stk_code')['c_hold_value']
           .sum()
           .rename('c_total_hold_mv')
           .reset_index())
    agg['c_crowd_score'] = agg['c_total_hold_mv'].rank(pct=True, method='average').round(4)
    agg['c_company_code'] = company_code
    return agg


def _calc_all_crowding(holdings: pd.DataFrame, company_map: pd.DataFrame) -> pd.DataFrame:
    """计算全市场 + 各公司维度的个股抱团度，一次返回所有结果"""
    mkt = _rank_by_mv(holdings, 'MKT')

    df = holdings.merge(company_map, on='c_fd_code', how='inner')
    company_parts = [
        _rank_by_mv(grp, company_code)
        for company_code, grp in df.groupby('c_company_code')
    ]

    return pd.concat([mkt] + company_parts, ignore_index=True)


# ==================== 主入口 ====================

def run(calc_date: str) -> None:
    """主入口，calc_date 须为半年报期：'2024-06-30' 或 '2024-12-31'"""
    assert calc_date[5:] in ('06-30', '12-31'), "calc_date 必须为半年报期"
    logger.info(f"计算 {calc_date}")

    with DorisConnector(ENV) as doris:
        fund_codes = _get_equity_funds(doris, calc_date)
        assert fund_codes, f"tb_fd_category 未找到 {calc_date} 的权益基金，请检查分类表是否已更新"
        logger.info(f"广义权益基金 {len(fund_codes)} 只")

        company_map = _get_fund_company_map(doris, fund_codes)
        logger.info(f"有公司映射的基金 {len(company_map)} 只，涉及 {company_map['c_company_code'].nunique()} 家公司")

        holdings = _query_full_holdings(doris, fund_codes, calc_date)
        logger.info(f"持仓记录: {len(holdings)}")

        result = _calc_all_crowding(holdings, company_map)
        result['c_report_date'] = pd.to_datetime(calc_date)
        doris.insert('tb_stk_crowding_score', result[OUTPUT_COLS])

    logger.info(f"写入完成 {calc_date}: {len(result)} 条（全市场+各公司）")


if __name__ == '__main__':
    from utils.common import should_run, ReportFreq
    # ── DS 调度模式 ──────────────────────────────────────────────────
    raw = "$[yyyyMMdd-1]"
    calc_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    ok, report_date = should_run(calc_date, ReportFreq.SEMI_ANNUAL)
    if ok:
        logger.info(f"触发执行，报告期={report_date}")
        run(report_date)
    else:
        logger.info(f"非披露窗口，跳过（calc_date={calc_date}）")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）────────────────
    # for dt in generate_report_dates('2025-12-31', 44)[::2]:
    #     run(dt)

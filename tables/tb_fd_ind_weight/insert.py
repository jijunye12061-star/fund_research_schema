import sys
from pathlib import Path


def _setup_path():
    """兼容本地和DS环境的路径适配"""
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

from utils.log import setup_logger
logger = setup_logger(__name__)

_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"  # 调度注入db_env参数；本地默认dev

SQL_TRADE_DATE = """
SELECT c_max_trade_date
FROM tytdata.tb_trade_calendar
WHERE c_date = :report_date
"""

SQL_HOLDINGS = """
SELECT p.c_fd_code,
       p.c_hold_value,
       LEFT(i.c_citic_code, 6) AS c_ind_code
FROM tytdata.tb_fd_portfolio_stk p
         JOIN tytdata.tb_stk_industry i
              ON p.c_stk_code = i.c_stk_code
                  AND i.c_trade_date = :trade_date
WHERE p.c_report_date = :report_date
  AND p.c_style IN ('02', '04')
  AND LENGTH(p.c_stk_code) = 6
  AND p.c_hold_value > 0

UNION ALL

SELECT p.c_fd_code,
       p.c_hold_value,
       CONCAT('025', SUBSTR(LEFT(i.c_citic_code, 6), 4, 3)) AS c_ind_code
FROM tytdata.tb_fd_portfolio_stk p
         JOIN tytdata.tb_stk_industry_hk i ON p.c_stk_code = i.c_stk_code
WHERE p.c_report_date = :report_date
  AND p.c_style IN ('02', '04')
  AND LENGTH(p.c_stk_code) = 5
  AND i.c_citic_code IS NOT NULL
  AND p.c_hold_value > 0

UNION ALL

SELECT p.c_fd_code,
       p.c_hold_value,
       LEFT(si.c_citic_code, 6) AS c_ind_code
FROM tytdata.tb_fd_portfolio_stk p
         JOIN tytdata.tb_stk_basic_info_hk hk ON p.c_stk_code = hk.c_stk_code
         JOIN tytdata.tb_stk_basic_info a ON hk.c_company_code = a.c_company_code
         JOIN tytdata.tb_stk_industry si
              ON a.c_stk_code = si.c_stk_code
                  AND si.c_trade_date = :trade_date
         LEFT JOIN tytdata.tb_stk_industry_hk i ON p.c_stk_code = i.c_stk_code
WHERE p.c_report_date = :report_date
  AND p.c_style IN ('02', '04')
  AND LENGTH(p.c_stk_code) = 5
  AND i.c_citic_code IS NULL
  AND p.c_hold_value > 0
"""

SQL_TOTAL_MV = """
SELECT c_fd_code, SUM(c_hold_value) AS total_mv
FROM tytdata.tb_fd_portfolio_stk
WHERE c_report_date = :report_date
  AND c_style IN ('02', '04')
  AND c_hold_value > 0
GROUP BY c_fd_code
"""

SQL_IND_NAMES = """
SELECT c_param_code, c_param_name
FROM tytdata.tb_dict_params
WHERE c_param_type = '中信行业分类'
  AND LENGTH(c_param_code) = 6
"""


def _query_data(doris: 'DorisConnector', report_date: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """拉取所有所需数据"""
    trade_date = doris.query(SQL_TRADE_DATE, report_date=report_date)['c_max_trade_date'].iloc[0]
    logger.info(f"报告期 {report_date} 对应交易日 {trade_date}")

    holdings = doris.query(SQL_HOLDINGS, report_date=report_date, trade_date=str(trade_date))
    total_mv = doris.query(SQL_TOTAL_MV, report_date=report_date)
    ind_names = doris.query(SQL_IND_NAMES)
    return holdings, total_mv, ind_names


def _calc_weights(holdings: pd.DataFrame, total_mv: pd.DataFrame) -> pd.DataFrame:
    """按基金×行业聚合，计算权重"""
    ind_mv = (holdings.groupby(['c_fd_code', 'c_ind_code'], as_index=False)['c_hold_value']
              .sum())
    result = ind_mv.merge(total_mv, on='c_fd_code', how='inner')
    result['c_weight'] = (result['c_hold_value'] / result['total_mv'] * 100).round(4)
    return result[['c_fd_code', 'c_ind_code', 'c_weight']]


def run(report_date: str) -> None:
    """主入口，report_date 须为半年报期：'2024-06-30' 或 '2024-12-31'"""
    assert report_date[5:] in ('06-30', '12-31'), "report_date 必须为半年报期"
    logger.info(f"开始计算 {report_date} 行业持仓权重")

    with DorisConnector(ENV) as doris:
        holdings, total_mv, ind_names = _query_data(doris, report_date)
        logger.info(f"持仓明细 {len(holdings)} 条，基金 {total_mv['c_fd_code'].nunique()} 只")

        result = _calc_weights(holdings, total_mv)
        result = result.merge(ind_names.rename(columns={'c_param_code': 'c_ind_code',
                                                         'c_param_name': 'c_ind_name'}),
                              on='c_ind_code', how='left')
        result['c_report_date'] = pd.to_datetime(report_date)
        result = result[['c_report_date', 'c_fd_code', 'c_ind_code', 'c_ind_name', 'c_weight']]

        doris.insert('tb_fd_ind_weight', result)

    logger.info(f"写入完成: {len(result)} 条")


if __name__ == '__main__':
    from utils.common import generate_report_dates, should_run, ReportFreq
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
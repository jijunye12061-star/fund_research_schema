"""
同时管理主动权益基金和二级债基的基金经理名单

输出6列：
  基金经理名称 | 权益基金代码 | 权益基金名称 | 二级债基代码 | 二级债基名称
  | 二级债基规模(亿) | 今年以来收益率(%) | 今年以来最大回撤(%)
"""
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
    raise RuntimeError("找不到 utils 目录")


_setup_path()

import pandas as pd
from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)

ENV = 'dev'

SCALE_REPORT_DATE = '2025-12-31'
SCALE_STYLE = '04'
LATEST_TRADE_DATE = '2026-04-08'


def _fetch_bond2_funds(doris: DorisConnector) -> pd.DataFrame:
    """拉取二级债基：初始代码 + 未清盘"""
    sql = """
    SELECT c_fd_code, c_short_name, c_manager_code, c_manager_name
    FROM tb_fd_basic_info
    WHERE c_class3_name = '混合债券型二级基金'
      AND c_terminate_date IS NULL
      AND (c_init_code = c_fd_code OR c_init_code IS NULL)
    """
    return doris.query(sql)


def _fetch_equity_funds(doris: DorisConnector) -> pd.DataFrame:
    """拉取主动权益基金：初始代码 + 未清盘，取各基金最新分类记录"""
    sql = """
    SELECT b.c_fd_code, b.c_short_name, b.c_manager_code, b.c_manager_name
    FROM tb_fd_basic_info b
    JOIN (
        SELECT c_fd_code, c_type1_code, c_type2_code,
               ROW_NUMBER() OVER (PARTITION BY c_fd_code ORDER BY c_report_date DESC) AS rn
        FROM tb_fd_category
    ) c ON b.c_fd_code = c.c_fd_code AND c.rn = 1
    WHERE c.c_type2_code = '001001'
      AND b.c_terminate_date IS NULL
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    """
    return doris.query(sql)


def _fetch_bond2_scale(doris: DorisConnector, fd_codes: list[str]) -> pd.DataFrame:
    """拉取二级债基规模（亿元），固定取 2025-12-31 年报"""
    sql = """
    SELECT c_fd_code, c_fund_nav_total
    FROM tb_fd_asset_allocation
    WHERE c_fd_code IN (:code_list)
      AND c_report_date = :report_date
      AND c_style = :style
      AND c_is_stat = -1
    """
    return doris.query_batch(sql, fd_codes, report_date=SCALE_REPORT_DATE, style=SCALE_STYLE)


def _fetch_bond2_perf(doris: DorisConnector, fd_codes: list[str]) -> pd.DataFrame:
    """拉取二级债基今年以来收益率和最大回撤"""
    sql = """
    SELECT c_fd_code, c_period_ret, c_mdd
    FROM tb_fd_perform_abs
    WHERE c_fd_code IN (:code_list)
      AND c_period_code = '07'
      AND c_trade_date = :trade_date
    """
    return doris.query_batch(sql, fd_codes, trade_date=LATEST_TRADE_DATE)


def _explode_managers(df: pd.DataFrame) -> pd.DataFrame:
    """将逗号分隔的 c_manager_code / c_manager_name 展开为每行一个经理"""
    rows = []
    for _, row in df.iterrows():
        codes = [c.strip() for c in str(row['c_manager_code']).split(',') if c.strip()]
        names = [n.strip() for n in str(row['c_manager_name']).split(',') if n.strip()]
        for i, code in enumerate(codes):
            name = names[i] if i < len(names) else ''
            rows.append({
                'c_fd_code': row['c_fd_code'],
                'c_short_name': row['c_short_name'],
                'c_manager_code': code,
                'c_manager_name': name,
            })
    return pd.DataFrame(rows)


def run():
    logger.info("开始拉取双重任务基金经理数据")

    with DorisConnector(ENV) as doris:
        df_bond2 = _fetch_bond2_funds(doris)
        df_equity = _fetch_equity_funds(doris)
        logger.info(f"二级债基: {len(df_bond2)} 只，主动权益: {len(df_equity)} 只")

    # 展开多基金经理
    bond2_mgr = _explode_managers(df_bond2)
    equity_mgr = _explode_managers(df_equity)

    # 找同时管理两类基金的经理
    dual_codes = set(bond2_mgr['c_manager_code']) & set(equity_mgr['c_manager_code'])
    logger.info(f"双重任务经理: {len(dual_codes)} 人")

    bond2_dual = bond2_mgr[bond2_mgr['c_manager_code'].isin(dual_codes)].copy()
    equity_dual = equity_mgr[equity_mgr['c_manager_code'].isin(dual_codes)].copy()

    # 拉二级债基规模和业绩
    bond2_codes = bond2_dual['c_fd_code'].unique().tolist()
    with DorisConnector(ENV) as doris:
        df_scale = _fetch_bond2_scale(doris, bond2_codes)
        df_perf = _fetch_bond2_perf(doris, bond2_codes)

    # 规模转亿元
    df_scale['c_fund_nav_total'] = pd.to_numeric(df_scale['c_fund_nav_total'], errors='coerce') / 1e8

    # 合并二级债基信息
    bond2_info = bond2_dual.merge(df_scale, on='c_fd_code', how='left')
    bond2_info = bond2_info.merge(df_perf, on='c_fd_code', how='left')

    # 每位经理的权益基金合并成一格
    equity_agg = (
        equity_dual.groupby('c_manager_code')
        .agg(权益基金代码=('c_fd_code', lambda x: ','.join(x)),
             权益基金名称=('c_short_name', lambda x: ','.join(x)))
        .reset_index()
    )

    result = bond2_info.merge(equity_agg, on='c_manager_code', how='left')

    output = result[[
        'c_manager_name',
        '权益基金代码',
        '权益基金名称',
        'c_fd_code',
        'c_short_name',
        'c_fund_nav_total',
        'c_period_ret',
        'c_mdd',
    ]].rename(columns={
        'c_manager_name': '基金经理',
        'c_fd_code': '二级债基代码',
        'c_short_name': '二级债基名称',
        'c_fund_nav_total': '二级债基规模(亿)',
        'c_period_ret': '今年以来收益率(%)',
        'c_mdd': '今年以来最大回撤(%)',
    }).sort_values(['基金经理', '二级债基代码'])

    output['二级债基规模(亿)'] = output['二级债基规模(亿)'].round(2)

    out_dir = Path(__file__).resolve().parent.parent / 'data'
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / 'dual_mandate_managers.xlsx'
    output.to_excel(out_path, index=False)

    logger.info(f"共 {len(output)} 行，已保存至 {out_path}")
    return output


if __name__ == '__main__':
    run()

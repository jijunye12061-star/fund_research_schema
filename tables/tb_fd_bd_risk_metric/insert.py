"""
债券信用评级与久期指标表
合并 FUND_IV_HOLDCREDITRISKO + FUND_IV_RISKSENSITIVE → 一基金一报告期一行
仅半年报(06-30)和年报(12-31)披露

@Author: 季俊晔
@Project: fund_research_db
"""
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
from typing import List

from utils.db_connector import OracleConnector, DorisConnector

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================

logger = logging.getLogger(__name__)

# 评级代码 → 字段映射
RATING_FIELD_MAP = {
    '101': 'c_short_high_mv',     # A-1
    '102': 'c_short_low_mv',      # A-1以下
    '201': 'c_long_high_mv',      # AAA
    '202': 'c_long_low_mv',       # AAA以下
}
# 300(未评级)需按RATETYPE区分短期/长期
UNRATED_FIELD_MAP = {
    '100': 'c_short_unrated_mv',
    '200': 'c_long_unrated_mv',
}

ALL_MV_FIELDS = list(RATING_FIELD_MAP.values()) + list(UNRATED_FIELD_MAP.values())


# ==================== 数据查询 ====================

def _get_fund_codes(report_date: str) -> List[str]:
    """获取存续初始基金代码列表"""
    sql = """
    SELECT c_fd_code
    FROM tytdata.tb_fd_basic_info
    WHERE c_estabdate <= :calc_date
      AND (c_terminate_date IS NULL OR c_terminate_date > :calc_date)
      AND c_fd_code = c_init_code
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, calc_date=report_date)
    return df['c_fd_code'].tolist() if not df.empty else []



def _query_credit_raw(fund_codes: List[str], report_date: str) -> pd.DataFrame:
    """查询信用评级原始数据"""
    sql = """
    SELECT
        SECURITYCODE AS c_fd_code,
        ENDDATE AS c_report_date,
        RATETYPE AS rate_type,
        RATING AS rating,
        FNVALUET AS market_value
    FROM TYTFUND.FUND_IV_HOLDCREDITRISKO
    WHERE SECURITYCODE IN (:code_list)
      AND ENDDATE = TO_DATE(:report_dt, 'YYYY-MM-DD')
      AND INVEST_TYPE = '1'
      AND EISDEL = '0'
    """
    with OracleConnector(ENV) as oracle:
        return oracle.query_batch(sql, code_list=fund_codes, report_dt=report_date)


def _query_duration_raw(fund_codes: List[str], report_date: str) -> pd.DataFrame:
    """查询久期原始数据（含债券投资市值）"""
    sql = """
    SELECT
        A.SECURITYCODE AS c_fd_code,
        A.ENDDATE AS c_report_date,
        A.FNVALUET AS nav_change,
        A.CHGRATIO AS change_ratio,
        B.BSUM AS bond_mv
    FROM TYTFUND.FUND_IV_RISKSENSITIVE A
    LEFT JOIN TYTFUND.FUND_IV_ASSETALLOCT B
        ON A.SECURITYCODE = B.FUNDCODE
        AND A.ENDDATE = B.ENDDATE
        AND B.STYLE IN ('01', '02', '03', '04')
    WHERE A.SECURITYCODE IN (:code_list)
      AND A.ENDDATE = TO_DATE(:report_dt, 'YYYY-MM-DD')
      AND A.VARIABLERISKCODE IN ('100101', '100102')
      AND A.EISDEL = '0'
    """
    with OracleConnector(ENV) as oracle:
        return oracle.query_batch(sql, code_list=fund_codes, report_dt=report_date)


# ==================== 指标计算 ====================

def _calc_credit_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """计算信用评级6项明细市值 + 3项汇总占比（向量化）"""
    df = df.dropna(subset=['MARKET_VALUE']).copy()
    df['MARKET_VALUE'] = df['MARKET_VALUE'].astype(float)

    # 合计(RATING=99)作为分母
    total = (df[df['RATING'] == '99']
             .groupby('C_FD_CODE')['MARKET_VALUE'].sum()
             .rename('total'))

    # 101/102/201/202 透视
    detail = df[df['RATING'].isin(RATING_FIELD_MAP)]
    pivot = (detail.groupby(['C_FD_CODE', 'RATING'])['MARKET_VALUE'].sum()
             .unstack(fill_value=0)
             .rename(columns=RATING_FIELD_MAP))

    # 300(未评级) 按RATETYPE透视
    unrated = df[df['RATING'] == '300']
    unrated_pivot = (unrated.groupby(['C_FD_CODE', 'RATE_TYPE'])['MARKET_VALUE'].sum()
                     .unstack(fill_value=0)
                     .rename(columns=UNRATED_FIELD_MAP))

    # 合并，inner join total确保分母有效
    result = pivot.join(unrated_pivot, how='outer').join(total, how='inner').fillna(0)
    for col in ALL_MV_FIELDS:
        if col not in result.columns:
            result[col] = 0.0

    result = result[result['total'] > 0].copy()

    # 汇总占比
    result['c_high_credit_ratio'] = (
        (result['c_short_high_mv'] + result['c_long_high_mv']) / result['total'] * 100
    ).round(4)
    result['c_low_credit_ratio'] = (
        (result['c_short_low_mv'] + result['c_long_low_mv']) / result['total'] * 100
    ).round(4)
    result['c_unrated_credit_ratio'] = (
        (result['c_short_unrated_mv'] + result['c_long_unrated_mv']) / result['total'] * 100
    ).round(4)

    for col in ALL_MV_FIELDS:
        result[col] = result[col].round(4)

    result = result.drop(columns='total').reset_index()
    result.columns = result.columns.str.lower()
    return result


def _calc_duration(df: pd.DataFrame) -> pd.DataFrame:
    """计算久期（利率敏感性反推）"""
    df.columns = df.columns.str.lower()
    for col in ['nav_change', 'change_ratio', 'bond_mv']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    grouped = df.groupby(['c_fd_code', 'c_report_date']).agg(
        nav_change_sum=('nav_change', lambda x: x.abs().sum()),
        change_ratio_sum=('change_ratio', 'sum'),
        c_bond_mv=('bond_mv', 'first')
    ).reset_index()

    valid = (grouped['change_ratio_sum'] != 0) & (grouped['c_bond_mv'] > 0)
    grouped = grouped[valid].copy()
    grouped['c_duration'] = (
        grouped['nav_change_sum'] / grouped['change_ratio_sum'] / grouped['c_bond_mv'] * 100
    ).round(4)

    return grouped[['c_fd_code', 'c_report_date', 'c_bond_mv', 'c_duration']]


# ==================== 主函数 ====================

def run(report_date: str) -> None:
    """主入口，report_date 须为半年报期：'2024-06-30' 或 '2024-12-31'"""
    assert report_date[5:] in ('06-30', '12-31'), "report_date 必须为半年报期"
    logger.info(f"计算 {report_date} 债券信用久期指标")

    fund_codes = _get_fund_codes(report_date)
    logger.info(f"基金共 {len(fund_codes)} 只")
    if not fund_codes:
        return

    credit_raw = _query_credit_raw(fund_codes, report_date)
    duration_raw = _query_duration_raw(fund_codes, report_date)
    logger.info(f"信用评级 {len(credit_raw)} 条, 久期 {len(duration_raw)} 条")

    credit_df = _calc_credit_ratios(credit_raw) if not credit_raw.empty else pd.DataFrame()
    duration_df = _calc_duration(duration_raw) if not duration_raw.empty else pd.DataFrame()

    if credit_df.empty and duration_df.empty:
        logger.warning("无有效数据")
        return

    if not credit_df.empty and not duration_df.empty:
        result = pd.merge(credit_df, duration_df,
                          on=['c_fd_code'], how='outer')
    elif not credit_df.empty:
        result = credit_df
    else:
        result = duration_df

    result['c_report_date'] = pd.to_datetime(result['c_report_date'])
    logger.info(f"生成 {len(result)} 条记录")

    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_bd_risk_metric', result)

    logger.info("写入完成")


if __name__ == '__main__':
    from utils.common import generate_report_dates, should_run, ReportFreq
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.SEMI_ANNUAL)
        if ok:
            run(report_date)
    else:
        # 历史補数：2015-06-30 起，21 期半年报
        for dt in generate_report_dates('2025-12-31', 42)[::2]:
            run(dt)
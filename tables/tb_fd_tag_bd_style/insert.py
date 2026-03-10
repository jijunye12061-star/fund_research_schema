#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
债券投资风格标签表
券种风格(三分类) + 杠杆风格 + 信用风格 + 久期风格

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
    raise RuntimeError("找不到 utils 目录")


_setup_path()

from dataclasses import dataclass
from functools import reduce
from typing import List

import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates, get_last_quarter_end
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================


@dataclass(frozen=True)
class Config:
    """标签配置参数"""
    # 回溯期数
    QUARTERLY_PERIODS: int = 8    # 券种+杠杆: 近8个季报
    HALFYEAR_PERIODS: int = 4     # 信用+久期: 近4个半年报

    # 券种风格(三分类)阈值
    SINGLE_STYLE: float = 70.0    # 单一风格阈值(%)
    MIXED_STYLE: float = 80.0     # 混合风格阈值(%)
    CF_RATIO_LOW: float = 0.66    # 信用/金融比下限
    CF_RATIO_HIGH: float = 1.5    # 信用/金融比上限
    COUPON_TIMING: float = 10.0   # 券种择时阈值(%)

    # 杠杆偏好(绝对值)
    LEV_HIGH_LOCKED: float = 1.6  # 定开-高杠杆
    LEV_LOW_LOCKED: float = 1.2   # 定开-低杠杆
    LEV_HIGH_OPEN: float = 1.3    # 非定开-高杠杆
    LEV_LOW_OPEN: float = 1.1     # 非定开-低杠杆
    # 杠杆择时(绝对值变动)
    LEV_TIMING_LOCKED: float = 0.15
    LEV_TIMING_OPEN: float = 0.10

    # 信用偏好(%)
    CREDIT_LOW: float = 40.0      # 信用下沉阈值
    CREDIT_HIGH: float = 40.0     # 中高信用阈值
    CREDIT_TIMING: float = 10.0   # 信用择时阈值(%)

    # 久期偏好(年)
    DUR_HIGH: float = 3.0
    DUR_MED: float = 2.0
    DUR_LOW: float = 1.0
    DUR_TIMING: float = 1.0       # 久期择时阈值(年)


CFG = Config()


# ==================== 日期工具 ====================

def _generate_half_year_dates(report_date: str, n: int) -> list[str]:
    """生成截至report_date的最近n个半年末日期(06-30/12-31)"""
    dt = pd.to_datetime(report_date)
    year = dt.year
    if dt >= pd.Timestamp(year, 12, 31):
        current = pd.Timestamp(year, 12, 31)
    elif dt >= pd.Timestamp(year, 6, 30):
        current = pd.Timestamp(year, 6, 30)
    else:
        current = pd.Timestamp(year - 1, 12, 31)

    dates = []
    while len(dates) < n:
        dates.append(current.strftime('%Y-%m-%d'))
        if current.month == 12:
            current = pd.Timestamp(current.year, 6, 30)
        else:
            current = pd.Timestamp(current.year - 1, 12, 31)
    return sorted(dates)


# ==================== 数据查询 ====================

def _get_fund_codes(report_date: str) -> List[str]:
    """获取初始基金代码列表(一级分类001-004，成立满两年)"""
    estab_cutoff = generate_report_dates(report_date, CFG.QUARTERLY_PERIODS)[0]
    sql = """
    SELECT DISTINCT a.c_fd_code
    FROM tytdata.tb_fd_category a
    INNER JOIN tytdata.tb_fd_basic_info b ON a.c_fd_code = b.c_fd_code
    WHERE a.c_report_date = :report_date
      AND a.c_type1_code IN ('001', '002', '003', '004')
      AND b.c_fd_code = b.c_init_code
      AND b.c_estabdate <= :estab_cutoff
      AND (b.c_terminate_date IS NULL OR b.c_terminate_date > :report_date)
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, report_date=report_date, estab_cutoff=estab_cutoff)
    return df['c_fd_code'].tolist() if not df.empty else []


def _get_locked_status(fund_codes: List[str]) -> pd.DataFrame:
    """获取基金定开状态"""
    sql = """
    SELECT c_fd_code, c_regular_open_status
    FROM tytdata.tb_fd_basic_info
    WHERE c_fd_code IN (:code_list)
    """
    with DorisConnector(ENV) as doris:
        return doris.query_batch(sql, code_list=fund_codes)


def _query_allocation_data(fund_codes: List[str],
                           report_dates: List[str]) -> pd.DataFrame:
    """查询资产配置数据(同报告期去重取最小style)"""
    sql = """
    SELECT c_fd_code, c_report_date,
           IFNULL(c_bd_total_mv, 0) AS c_bd_total_mv,
           IFNULL(c_bd_treasury_mv, 0) AS c_bd_treasury_mv,
           IFNULL(c_bd_policy_mv, 0) AS c_bd_policy_mv,
           IFNULL(c_bd_central_bank_mv, 0) AS c_bd_central_bank_mv,
           IFNULL(c_bd_local_gov_mv, 0) AS c_bd_local_gov_mv,
           IFNULL(c_bd_corporate_mv, 0) AS c_bd_corporate_mv,
           IFNULL(c_bd_mtn_mv, 0) AS c_bd_mtn_mv,
           IFNULL(c_bd_short_term_mv, 0) AS c_bd_short_term_mv,
           IFNULL(c_bd_financial_mv, 0) AS c_bd_financial_mv,
           IFNULL(c_bd_deposit_cert_mv, 0) AS c_bd_deposit_cert_mv,
           IFNULL(c_other_abs_mv, 0) AS c_other_abs_mv,
           IFNULL(c_fund_total_asset, 0) AS c_fund_total_asset,
           IFNULL(c_fund_nav_total, 0) AS c_fund_nav_total
    FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY c_fd_code, c_report_date ORDER BY c_style
        ) AS rn
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_report_date BETWEEN :start_date AND :end_date
    ) t WHERE rn = 1
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, start_date=report_dates[0],
                         end_date=report_dates[-1])
    if df.empty:
        return df

    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    valid_dates = pd.to_datetime(report_dates)
    return df[
        df['c_fd_code'].isin(fund_codes) &
        df['c_report_date'].isin(valid_dates)
    ].copy()


def _query_risk_metric_data(fund_codes: List[str],
                            halfyear_dates: List[str]) -> pd.DataFrame:
    """查询信用评级+久期数据"""
    sql = """
    SELECT c_fd_code, c_report_date,
           c_high_credit_ratio, c_low_credit_ratio, c_duration
    FROM tytdata.tb_fd_bd_risk_metric
    WHERE c_report_date BETWEEN :start_date AND :end_date
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, start_date=halfyear_dates[0],
                         end_date=halfyear_dates[-1])
    if df.empty:
        return df

    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    valid_dates = pd.to_datetime(halfyear_dates)
    return df[
        df['c_fd_code'].isin(fund_codes) &
        df['c_report_date'].isin(valid_dates)
    ].copy()


# ==================== 通用计算 ====================

def _calc_avg_and_change(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """计算各基金的均值和环比变动绝对值均值"""
    sorted_df = df.sort_values(['c_fd_code', 'c_report_date'])
    avg = sorted_df.groupby('c_fd_code')[value_col].mean()
    chg = sorted_df.groupby('c_fd_code')[value_col].apply(
        lambda x: x.diff().abs().mean()
    )
    return pd.DataFrame({
        f'{value_col}_avg': avg,
        f'{value_col}_chg_avg': chg,
    }).reset_index()


# ==================== 券种占比计算 ====================

def _calc_bond_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """计算各券种占债券总市值比例(%)和杠杆率"""
    result = df[['c_fd_code', 'c_report_date']].copy()
    bd_total = df['c_bd_total_mv']
    has_bond = bd_total > 0

    # 利率债 = 国债+政金债+央票+地方债
    rate_mv = (df['c_bd_treasury_mv'] + df['c_bd_policy_mv']
               + df['c_bd_central_bank_mv'] + df['c_bd_local_gov_mv'])
    # 信用债 = 企业债+中票+短融+ABS
    credit_mv = (df['c_bd_corporate_mv'] + df['c_bd_mtn_mv']
                 + df['c_bd_short_term_mv'] + df['c_other_abs_mv'])
    # 金融债 = 金融债+同存-政金债
    fin_mv = (df['c_bd_financial_mv'] + df['c_bd_deposit_cert_mv']
              - df['c_bd_policy_mv'])

    result['rate_bd'] = np.where(has_bond, rate_mv / bd_total * 100, 0)
    result['credit_bd'] = np.where(has_bond, credit_mv / bd_total * 100, 0)
    result['fin_bd'] = np.where(has_bond, fin_mv / bd_total * 100, 0)

    # 杠杆率 = 总资产/净资产
    has_nav = df['c_fund_nav_total'] > 0
    result['leverage'] = np.where(
        has_nav, df['c_fund_total_asset'] / df['c_fund_nav_total'], np.nan
    )
    return result


# ==================== 券种风格标签 ====================

def _assign_coupon_labels(df: pd.DataFrame) -> pd.DataFrame:
    """三分类券种风格打标"""
    r, c, f = df['c_rate_bd_pos_avg'], df['c_credit_bd_pos_avg'], df['c_fin_bd_pos_avg']
    cf_ratio = np.where(f > 0, c / f, np.inf)

    # 第一层: 单一风格 ≥70%
    s1 = [r >= CFG.SINGLE_STYLE, c >= CFG.SINGLE_STYLE, f >= CFG.SINGLE_STYLE]
    not_s1 = ~(s1[0] | s1[1] | s1[2])

    # 第二层: 混合风格 ≥80%
    s2 = [
        not_s1 & (r + f >= CFG.MIXED_STYLE),
        not_s1 & (c + f >= CFG.MIXED_STYLE) & (cf_ratio >= CFG.CF_RATIO_LOW) & (cf_ratio <= CFG.CF_RATIO_HIGH),
        not_s1 & (c + f >= CFG.MIXED_STYLE) & (cf_ratio < CFG.CF_RATIO_LOW),
        not_s1 & (c + f >= CFG.MIXED_STYLE) & (cf_ratio > CFG.CF_RATIO_HIGH),
    ]
    labels = (['利率风格', '信用风格', '金融风格']
              + ['利率+金融风格', '信用+金融风格', '信用+金融风格-偏金融', '信用+金融风格-偏信用'])

    df['c_bd_type_style'] = np.select(s1 + s2, labels, default='均衡配置')
    df['c_bd_type_timing'] = np.where(
        np.minimum(df['c_rate_bd_chg_avg'], df['c_credit_bd_chg_avg']) >= CFG.COUPON_TIMING,
        '择时', '不择时'
    )
    return df


def _label_coupon_style(bond_df: pd.DataFrame) -> pd.DataFrame:
    """计算券种风格标签"""
    rate = _calc_avg_and_change(bond_df, 'rate_bd')
    credit = _calc_avg_and_change(bond_df, 'credit_bd')
    fin = _calc_avg_and_change(bond_df, 'fin_bd')

    result = rate.merge(credit, on='c_fd_code').merge(fin, on='c_fd_code')
    result = result.rename(columns={
        'rate_bd_avg': 'c_rate_bd_pos_avg',
        'credit_bd_avg': 'c_credit_bd_pos_avg',
        'fin_bd_avg': 'c_fin_bd_pos_avg',
        'rate_bd_chg_avg': 'c_rate_bd_chg_avg',
        'credit_bd_chg_avg': 'c_credit_bd_chg_avg',
    })
    result = _assign_coupon_labels(result)

    keep = ['c_fd_code', 'c_rate_bd_pos_avg', 'c_credit_bd_pos_avg',
            'c_fin_bd_pos_avg', 'c_rate_bd_chg_avg', 'c_credit_bd_chg_avg',
            'c_bd_type_style', 'c_bd_type_timing']
    return result[keep]


# ==================== 杠杆风格标签 ====================

def _label_leverage_style(bond_df: pd.DataFrame,
                          locked_df: pd.DataFrame) -> pd.DataFrame:
    """计算杠杆风格标签(定开/非定开分档)"""
    stats = _calc_avg_and_change(bond_df, 'leverage')
    result = stats.rename(columns={
        'leverage_avg': 'c_leverage_avg',
        'leverage_chg_avg': 'c_leverage_chg_avg',
    })
    result = result.merge(locked_df, on='c_fd_code', how='left')
    is_locked = result['c_regular_open_status'] == '1'

    # 杠杆偏好
    result['c_leverage_pref'] = np.select(
        [
            is_locked & (result['c_leverage_avg'] > CFG.LEV_HIGH_LOCKED),
            is_locked & (result['c_leverage_avg'] <= CFG.LEV_LOW_LOCKED),
            ~is_locked & (result['c_leverage_avg'] > CFG.LEV_HIGH_OPEN),
            ~is_locked & (result['c_leverage_avg'] <= CFG.LEV_LOW_OPEN),
        ],
        ['高杠杆', '低杠杆', '高杠杆', '低杠杆'],
        default='中杠杆'
    )
    # 杠杆择时
    result['c_leverage_timing'] = np.select(
        [
            is_locked & (result['c_leverage_chg_avg'] >= CFG.LEV_TIMING_LOCKED),
            ~is_locked & (result['c_leverage_chg_avg'] >= CFG.LEV_TIMING_OPEN),
        ],
        ['择时', '择时'],
        default='不择时'
    )

    keep = ['c_fd_code', 'c_leverage_avg', 'c_leverage_chg_avg',
            'c_leverage_pref', 'c_leverage_timing']
    return result[keep]


# ==================== 信用风格标签 ====================

def _label_credit_style(risk_df: pd.DataFrame) -> pd.DataFrame:
    """计算信用偏好和信用择时标签"""
    df = risk_df.dropna(subset=['c_high_credit_ratio']).copy()
    if df.empty:
        return pd.DataFrame()

    high = _calc_avg_and_change(df, 'c_high_credit_ratio')
    low = _calc_avg_and_change(df, 'c_low_credit_ratio')
    result = high.merge(low, on='c_fd_code')

    result = result.rename(columns={
        'c_high_credit_ratio_avg': 'c_high_credit_avg',
        'c_low_credit_ratio_avg': 'c_low_credit_avg',
        'c_low_credit_ratio_chg_avg': 'c_low_credit_chg_avg',
    })

    result['c_credit_pref'] = np.select(
        [
            result['c_low_credit_avg'] >= CFG.CREDIT_LOW,
            result['c_high_credit_avg'] >= CFG.CREDIT_HIGH,
        ],
        ['信用下沉', '中高信用'],
        default='无明显偏好'
    )
    result['c_credit_timing'] = np.where(
        result['c_low_credit_chg_avg'] >= CFG.CREDIT_TIMING,
        '择时', '不择时'
    )

    keep = ['c_fd_code', 'c_high_credit_avg', 'c_low_credit_avg',
            'c_low_credit_chg_avg', 'c_credit_pref', 'c_credit_timing']
    return result[keep]


# ==================== 久期风格标签 ====================

def _label_duration_style(risk_df: pd.DataFrame) -> pd.DataFrame:
    """计算久期偏好和久期择时标签"""
    df = risk_df.dropna(subset=['c_duration']).copy()
    if df.empty:
        return pd.DataFrame()

    stats = _calc_avg_and_change(df, 'c_duration')
    result = stats.rename(columns={
        'c_duration_avg': 'c_duration_avg',
        'c_duration_chg_avg': 'c_duration_chg_avg',
    })

    result['c_duration_pref'] = np.select(
        [
            result['c_duration_avg'] >= CFG.DUR_HIGH,
            result['c_duration_avg'] >= CFG.DUR_MED,
            result['c_duration_avg'] >= CFG.DUR_LOW,
        ],
        ['长久期', '中长久期', '中短久期'],
        default='短久期'
    )
    result['c_duration_timing'] = np.where(
        result['c_duration_chg_avg'] >= CFG.DUR_TIMING,
        '择时', '不择时'
    )

    keep = ['c_fd_code', 'c_duration_avg', 'c_duration_chg_avg',
            'c_duration_pref', 'c_duration_timing']
    return result[keep]


# ==================== 主函数 ====================

def _merge_labels(*label_dfs: pd.DataFrame) -> pd.DataFrame:
    """合并各维度标签(outer join)"""
    valid = [df for df in label_dfs if not df.empty]
    if not valid:
        return pd.DataFrame()
    return reduce(lambda l, r: pd.merge(l, r, on='c_fd_code', how='outer'), valid)


def run(calc_date: str):
    """主入口，传入任意日期自动定位上季末报告期"""
    report_date = get_last_quarter_end(calc_date)
    logger.info(f"生成 {report_date} 债券投资风格标签")

    # 基金范围
    fund_codes = _get_fund_codes(report_date)
    if not fund_codes:
        logger.warning("无符合条件的基金")
        return
    logger.info(f"基金 {len(fund_codes)} 只")

    locked_df = _get_locked_status(fund_codes)

    # ---- 券种+杠杆维度(近8期季报) ----
    quarterly_dates = generate_report_dates(report_date, CFG.QUARTERLY_PERIODS)
    alloc_df = _query_allocation_data(fund_codes, quarterly_dates)
    logger.info(f"资产配置数据 {len(alloc_df)} 条")

    coupon_labels = leverage_labels = pd.DataFrame()
    if not alloc_df.empty:
        bond_df = _calc_bond_ratios(alloc_df)
        coupon_labels = _label_coupon_style(bond_df)
        leverage_labels = _label_leverage_style(bond_df, locked_df)

    # ---- 信用+久期维度(近4个半年报期) ----
    halfyear_dates = _generate_half_year_dates(report_date, CFG.HALFYEAR_PERIODS)
    risk_df = _query_risk_metric_data(fund_codes, halfyear_dates)
    logger.info(f"信用久期数据 {len(risk_df)} 条")

    credit_labels = _label_credit_style(risk_df) if not risk_df.empty else pd.DataFrame()
    duration_labels = _label_duration_style(risk_df) if not risk_df.empty else pd.DataFrame()

    # ---- 合并写入 ----
    result = _merge_labels(coupon_labels, leverage_labels, credit_labels, duration_labels)
    if result.empty:
        logger.warning("无有效标签数据")
        return

    result['c_report_date'] = pd.to_datetime(report_date)
    result = result.merge(
        locked_df.rename(columns={'c_regular_open_status': 'c_is_locked_fund'}),
        on='c_fd_code', how='left'
    )
    logger.info(f"生成 {len(result)} 条记录")

    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_tag_bd_style', result)
    logger.info("写入完成")


if __name__ == '__main__':
    run('2026-02-28')
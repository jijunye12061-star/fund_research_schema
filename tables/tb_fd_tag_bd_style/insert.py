#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
债券投资风格标签生成

四个维度: 券种风格、杠杆风格、信用风格、久期风格
数据源: tb_fd_asset_allocation(季度) + tb_fd_bd_risk_metric(半年度)

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
from typing import List

import numpy as np
import pandas as pd
from utils.db_connector import DorisConnector
from utils.common import generate_report_dates
from utils.log import setup_logger
logger = setup_logger(__name__)

# ============================================================
ENV = 'dev'  # 切换环境: 'dev' | 'prod'
# ============================================================


# ============================================================
# 配置
# ============================================================
@dataclass(frozen=True)
class BdStyleConfig:
    """债券风格标签阈值配置"""
    # 回溯期数
    QUARTERLY_PERIODS: int = 8   # 券种/杠杆: 近8个季报
    HALF_YEAR_PERIODS: int = 4   # 信用/久期: 近4个半年报

    # 券种风格 — 三分类阈值
    SINGLE_STYLE: float = 70.0   # 单一风格阈值(%)
    MIXED_STYLE: float = 80.0    # 混合风格阈值(%)
    CREDIT_FIN_RATIO_LOW: float = 0.66   # 信用/金融比下限
    CREDIT_FIN_RATIO_HIGH: float = 1.5   # 信用/金融比上限

    # 券种择时: 三个变动中第二大值 ≥ 阈值
    TIMING_COUPON: float = 10.0

    # 杠杆偏好 — 定开/非定开分档
    LEVERAGE_HIGH_LOCKED: float = 1.6
    LEVERAGE_LOW_LOCKED: float = 1.2
    LEVERAGE_HIGH_NORMAL: float = 1.3
    LEVERAGE_LOW_NORMAL: float = 1.1

    # 杠杆择时 — 绝对变动
    TIMING_LEVERAGE_LOCKED: float = 0.15
    TIMING_LEVERAGE_NORMAL: float = 0.10

    # 信用偏好（优先级: 信用下沉 > 中高信用）
    CREDIT_LOW_THRESHOLD: float = 40.0   # 信用下沉: 低评级占比 ≥ 40%
    CREDIT_HIGH_THRESHOLD: float = 40.0  # 中高信用: 高评级占比 ≥ 40%

    # 信用择时
    TIMING_CREDIT: float = 10.0  # 低评级变动 ≥ 10%

    # 久期偏好
    DURATION_HIGH: float = 3.0    # 长久期
    DURATION_MEDIUM: float = 2.0  # 中长久期
    DURATION_LOW: float = 1.0     # 中短久期

    # 久期择时
    TIMING_DURATION: float = 1.0  # 久期变动 ≥ 1年


CFG = BdStyleConfig()


# ============================================================
# 数据查询
# ============================================================
def _get_fund_info(report_date: str, earliest_date: str) -> pd.DataFrame:
    """获取基金代码与定开信息"""
    sql = """
    SELECT DISTINCT
        a.c_fd_code,
        IFNULL(b.c_regular_open_status, '0') AS c_is_locked
    FROM tytdata.tb_fd_category a
    JOIN tytdata.tb_fd_basic_info b ON a.c_fd_code = b.c_fd_code
    WHERE a.c_report_date = :report_date
      AND a.c_type1_code IN ('001', '002', '003', '004')
      AND b.c_fd_code = b.c_init_code
      AND b.c_estabdate <= :earliest_date
      AND (b.c_terminate_date IS NULL OR b.c_terminate_date > :report_date)
    """
    with DorisConnector(ENV) as doris:
        df = doris.query(sql, report_date=report_date,
                         earliest_date=earliest_date)
    logger.info(f"筛选基金 {len(df)} 只（成立早于 {earliest_date}）")
    return df


def _query_allocation(fund_codes: List[str], report_dates: List[str]) -> pd.DataFrame:
    """查询资产配置数据（近八期季报）"""
    sql = """
    WITH ranked AS (
        SELECT c_fd_code, c_report_date,
               IFNULL(c_fund_total_asset, 0) AS total_asset,
               IFNULL(c_fund_nav_total, 0)   AS nav_total,
               IFNULL(c_bd_total_mv, 0)      AS bd_total_mv,
               IFNULL(c_bd_treasury_mv, 0)     AS treasury_mv,
               IFNULL(c_bd_policy_mv, 0)       AS policy_mv,
               IFNULL(c_bd_central_bank_mv, 0) AS central_bank_mv,
               IFNULL(c_bd_local_gov_mv, 0)    AS local_gov_mv,
               IFNULL(c_bd_financial_mv, 0)    AS financial_mv,
               IFNULL(c_bd_deposit_cert_mv, 0) AS deposit_cert_mv,
               IFNULL(c_bd_corporate_mv, 0)    AS corporate_mv,
               IFNULL(c_bd_mtn_mv, 0)          AS mtn_mv,
               IFNULL(c_bd_short_term_mv, 0)   AS short_term_mv,
               IFNULL(c_other_abs_mv, 0)       AS abs_mv,
               ROW_NUMBER() OVER (
                   PARTITION BY c_fd_code, c_report_date ORDER BY c_style
               ) AS rn
        FROM tytdata.tb_fd_asset_allocation
        WHERE c_fd_code IN (:code_list)
          AND c_report_date BETWEEN :start_date AND :end_date
    )
    SELECT * FROM ranked WHERE rn = 1
    """
    with DorisConnector(ENV) as doris:
        df = doris.query_batch(sql, code_list=fund_codes,
                               start_date=report_dates[0],
                               end_date=report_dates[-1])

    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    target = pd.to_datetime(report_dates)
    return df[df['c_report_date'].isin(target)].copy()


def _query_risk_metric(fund_codes: List[str], half_year_dates: List[str]) -> pd.DataFrame:
    """查询信用评级与久期数据（近四期半年报）"""
    sql = """
    SELECT c_fd_code, c_report_date,
           c_high_credit_ratio, c_low_credit_ratio, c_duration
    FROM tytdata.tb_fd_bd_risk_metric
    WHERE c_fd_code IN (:code_list)
          AND c_report_date BETWEEN :start_date AND :end_date
    """
    with DorisConnector(ENV) as doris:
        df = doris.query_batch(sql, code_list=fund_codes,
                               start_date=half_year_dates[0],
                               end_date=half_year_dates[-1])

    df['c_report_date'] = pd.to_datetime(df['c_report_date'])
    target = pd.to_datetime(half_year_dates)
    return df[df['c_report_date'].isin(target)].copy()


# ============================================================
# 通用计算
# ============================================================
def _calc_avg_and_chg(df: pd.DataFrame, group_col: str,
                      value_cols: List[str]) -> pd.DataFrame:
    """计算均值和环比变动绝对值均值"""
    sorted_df = df.sort_values([group_col, 'c_report_date'])

    # 均值
    avg_df = sorted_df.groupby(group_col)[value_cols].mean()
    avg_df.columns = [f'{c}_avg' for c in avg_df.columns]

    # 环比变动绝对值均值
    chg_df = sorted_df.groupby(group_col)[value_cols].apply(
        lambda g: g.diff().abs().mean()
    )
    chg_df.columns = [f'{c}_chg_avg' for c in chg_df.columns]

    return avg_df.join(chg_df).reset_index()


# ============================================================
# 券种风格
# ============================================================
def _calc_bond_ratios(alloc_df: pd.DataFrame) -> pd.DataFrame:
    """计算各券种占债券总市值比(%)"""
    df = alloc_df.copy()
    mask = df['bd_total_mv'] > 0

    # 利率债 = 国债 + 政策性金融债 + 央行票据 + 地方政府债
    df['rate_ratio'] = 0.0
    df.loc[mask, 'rate_ratio'] = (
        (df['treasury_mv'] + df['policy_mv'] + df['central_bank_mv'] + df['local_gov_mv'])
        / df['bd_total_mv'] * 100
    )

    # 信用债 = 企业债 + 中期票据 + 企业短融 + 资产支持证券
    df['credit_ratio'] = 0.0
    df.loc[mask, 'credit_ratio'] = (
        (df['corporate_mv'] + df['mtn_mv'] + df['short_term_mv'] + df['abs_mv'])
        / df['bd_total_mv'] * 100
    )

    # 金融债 = 金融债(含政策性) - 政策性金融债 + 同业存单
    df['fin_ratio'] = 0.0
    df.loc[mask, 'fin_ratio'] = (
        (df['financial_mv'] - df['policy_mv'] + df['deposit_cert_mv'])
        / df['bd_total_mv'] * 100
    )

    # 杠杆率
    nav_mask = df['nav_total'] > 0
    df['leverage'] = np.nan
    df.loc[nav_mask, 'leverage'] = df['total_asset'] / df['nav_total']

    return df[['c_fd_code', 'c_report_date',
               'rate_ratio', 'credit_ratio', 'fin_ratio', 'leverage', 'bd_total_mv']].copy()


def _label_bond_type_style(avg_df: pd.DataFrame) -> pd.DataFrame:
    """生成券种风格标签（三分类）"""
    df = avg_df.copy()
    rate = df['rate_ratio_avg']
    credit = df['credit_ratio_avg']
    fin = df['fin_ratio_avg']

    # 第一层: 单一风格 ≥70%
    cond_first = [
        rate >= CFG.SINGLE_STYLE,
        credit >= CFG.SINGLE_STYLE,
        fin >= CFG.SINGLE_STYLE,
    ]
    label_first = ['利率风格', '信用风格', '金融风格']

    # 第二层: 混合风格 ≥80%
    not_single = ~(cond_first[0] | cond_first[1] | cond_first[2])
    rate_fin_sum = rate + fin
    credit_fin_sum = credit + fin
    credit_fin_ratio = np.where(fin > 0, credit / fin, np.inf)

    cond_second = [
        not_single & (rate_fin_sum >= CFG.MIXED_STYLE),
        not_single & (credit_fin_sum >= CFG.MIXED_STYLE)
        & (credit_fin_ratio >= CFG.CREDIT_FIN_RATIO_LOW)
        & (credit_fin_ratio <= CFG.CREDIT_FIN_RATIO_HIGH),
        not_single & (credit_fin_sum >= CFG.MIXED_STYLE)
        & (credit_fin_ratio < CFG.CREDIT_FIN_RATIO_LOW),
        not_single & (credit_fin_sum >= CFG.MIXED_STYLE)
        & (credit_fin_ratio > CFG.CREDIT_FIN_RATIO_HIGH),
    ]
    label_second = ['利率+金融风格', '信用+金融风格', '信用+金融风格-偏金融', '信用+金融风格-偏信用']

    df['c_bd_type_style'] = np.select(
        cond_first + cond_second,
        label_first + label_second,
        default='均衡配置'
    )

    # 择时: 三个券种变动中第二大值 ≥ 阈值（至少两个维度有显著变动）
    chg_cols = ['rate_ratio_chg_avg', 'credit_ratio_chg_avg', 'fin_ratio_chg_avg']
    chg_matrix = df[chg_cols].values
    second_largest = np.sort(chg_matrix, axis=1)[:, -2]  # 每行第二大值
    df['c_bd_type_timing'] = np.where(
        second_largest >= CFG.TIMING_COUPON, '择时', '不择时'
    )

    return df


# ============================================================
# 杠杆风格
# ============================================================
def _label_leverage_style(avg_df: pd.DataFrame,
                          fund_info: pd.DataFrame) -> pd.DataFrame:
    """生成杠杆风格标签"""
    df = avg_df.merge(fund_info, on='c_fd_code')
    is_locked = df['c_is_locked'] == '1'

    # 偏好标签: 定开/非定开不同阈值
    high = np.where(is_locked, CFG.LEVERAGE_HIGH_LOCKED, CFG.LEVERAGE_HIGH_NORMAL)
    low = np.where(is_locked, CFG.LEVERAGE_LOW_LOCKED, CFG.LEVERAGE_LOW_NORMAL)

    df['c_leverage_pref'] = np.select(
        [df['leverage_avg'] > high, df['leverage_avg'] <= low],
        ['高杠杆', '低杠杆'],
        default='中杠杆'
    )

    # 择时标签
    threshold = np.where(is_locked, CFG.TIMING_LEVERAGE_LOCKED, CFG.TIMING_LEVERAGE_NORMAL)
    df['c_leverage_timing'] = np.where(
        df['leverage_chg_avg'] >= threshold, '择时', '不择时'
    )

    return df


# ============================================================
# 信用风格
# ============================================================
def _label_credit_style(avg_df: pd.DataFrame) -> pd.DataFrame:
    """生成信用风格标签（优先级: 信用下沉 > 中高信用）"""
    df = avg_df.copy()

    df['c_credit_pref'] = np.select(
        [
            df['c_low_credit_ratio_avg'] >= CFG.CREDIT_LOW_THRESHOLD,
            df['c_high_credit_ratio_avg'] >= CFG.CREDIT_HIGH_THRESHOLD,
        ],
        ['信用下沉', '中高信用'],
        default='无明显偏好'
    )

    df['c_credit_timing'] = np.where(
        df['c_low_credit_ratio_chg_avg'] >= CFG.TIMING_CREDIT,
        '择时', '不择时'
    )

    return df


# ============================================================
# 久期风格
# ============================================================
def _label_duration_style(avg_df: pd.DataFrame) -> pd.DataFrame:
    """生成久期风格标签"""
    df = avg_df.copy()

    df['c_duration_pref'] = np.select(
        [
            df['c_duration_avg'] >= CFG.DURATION_HIGH,
            df['c_duration_avg'] >= CFG.DURATION_MEDIUM,
            df['c_duration_avg'] >= CFG.DURATION_LOW,
        ],
        ['长久期', '中长久期', '中短久期'],
        default='短久期'
    )

    df['c_duration_timing'] = np.where(
        df['c_duration_chg_avg'] >= CFG.TIMING_DURATION,
        '择时', '不择时'
    )

    return df


# ============================================================
# 结果组装
# ============================================================
def _build_result(bond_type_df: pd.DataFrame,
                  leverage_df: pd.DataFrame,
                  credit_df: pd.DataFrame,
                  duration_df: pd.DataFrame,
                  report_date: str) -> pd.DataFrame:
    """组装最终结果，对齐输出字段"""
    # 券种维度
    bt = bond_type_df[['c_fd_code',
                       'rate_ratio_avg', 'credit_ratio_avg', 'fin_ratio_avg',
                       'rate_ratio_chg_avg', 'credit_ratio_chg_avg', 'fin_ratio_chg_avg',
                       'c_bd_type_style', 'c_bd_type_timing']].rename(columns={
        'rate_ratio_avg': 'c_rate_bd_pos_avg',
        'credit_ratio_avg': 'c_credit_bd_pos_avg',
        'fin_ratio_avg': 'c_fin_bd_pos_avg',
        'rate_ratio_chg_avg': 'c_rate_bd_chg_avg',
        'credit_ratio_chg_avg': 'c_credit_bd_chg_avg',
        'fin_ratio_chg_avg': 'c_fin_bd_chg_avg',
    })

    # 杠杆维度
    lv = leverage_df[['c_fd_code', 'c_is_locked',
                      'leverage_avg', 'leverage_chg_avg',
                      'c_leverage_pref', 'c_leverage_timing']].rename(columns={
        'leverage_avg': 'c_leverage_avg',
        'leverage_chg_avg': 'c_leverage_chg_avg',
    })

    # 信用维度
    if not credit_df.empty:
        cr = credit_df[['c_fd_code',
                        'c_high_credit_ratio_avg', 'c_low_credit_ratio_avg',
                        'c_low_credit_ratio_chg_avg',
                        'c_credit_pref', 'c_credit_timing']].rename(columns={
            'c_high_credit_ratio_avg': 'c_high_credit_avg',
            'c_low_credit_ratio_avg': 'c_low_credit_avg',
            'c_low_credit_ratio_chg_avg': 'c_low_credit_chg_avg',
        })
    else:
        cr = pd.DataFrame(columns=['c_fd_code'])

    # 久期维度
    if not duration_df.empty:
        du = duration_df[['c_fd_code',
                          'c_duration_avg', 'c_duration_chg_avg',
                          'c_duration_pref', 'c_duration_timing']]
    else:
        du = pd.DataFrame(columns=['c_fd_code'])

    # outer merge: 不同维度覆盖范围可能不同
    from functools import reduce
    dfs = [lv, bt, cr, du]
    result = reduce(lambda l, r: pd.merge(l, r, on='c_fd_code', how='outer'), dfs)

    result['c_report_date'] = pd.to_datetime(report_date)

    # 数值列四舍五入
    numeric_cols = result.select_dtypes(include='number').columns
    result[numeric_cols] = result[numeric_cols].round(4)

    return result


# ============================================================
# 主入口
# ============================================================
def run(report_date: str) -> None:
    """主入口，report_date 为报告期如 '2025-12-31'"""
    logger.info(f"开始生成 {report_date} 债券投资风格标签")

    # 生成回溯日期
    quarter_dates = generate_report_dates(report_date, CFG.QUARTERLY_PERIODS)
    half_year_dates = [d for d in quarter_dates if d[5:] in ('06-30', '12-31')]

    # 获取基金池
    fund_info = _get_fund_info(report_date, earliest_date=quarter_dates[0])
    if fund_info.empty:
        logger.warning("无符合条件的基金")
        return None
    fund_codes = fund_info['c_fd_code'].tolist()

    # ---- 券种 + 杠杆（季度数据）----
    alloc_raw = _query_allocation(fund_codes, quarter_dates)
    logger.info(f"资产配置数据 {len(alloc_raw)} 条")

    bond_ratio_df = _calc_bond_ratios(alloc_raw)

    # 排除全期无债券持仓的基金
    has_bond = bond_ratio_df.groupby('c_fd_code')['bd_total_mv'].max() > 0
    bond_ratio_df = bond_ratio_df[bond_ratio_df['c_fd_code'].isin(has_bond[has_bond].index)]

    # 券种均值 + 变动
    bond_avg = _calc_avg_and_chg(bond_ratio_df, 'c_fd_code',
                                 ['rate_ratio', 'credit_ratio', 'fin_ratio'])
    bond_type_df = _label_bond_type_style(bond_avg)

    # 杠杆均值 + 变动
    lever_avg = _calc_avg_and_chg(bond_ratio_df, 'c_fd_code', ['leverage'])
    leverage_df = _label_leverage_style(lever_avg, fund_info)

    # ---- 信用 + 久期（半年度数据）----
    if half_year_dates:
        risk_raw = _query_risk_metric(fund_codes, half_year_dates)
        logger.info(f"信用久期数据 {len(risk_raw)} 条")
    else:
        risk_raw = pd.DataFrame()

    # 信用
    if not risk_raw.empty and 'c_high_credit_ratio' in risk_raw.columns:
        credit_data = risk_raw.dropna(subset=['c_high_credit_ratio'])
        if not credit_data.empty:
            credit_avg = _calc_avg_and_chg(
                credit_data, 'c_fd_code',
                ['c_high_credit_ratio', 'c_low_credit_ratio']
            )
            credit_df = _label_credit_style(credit_avg)
        else:
            credit_df = pd.DataFrame()
    else:
        credit_df = pd.DataFrame()

    # 久期
    if not risk_raw.empty and 'c_duration' in risk_raw.columns:
        duration_data = risk_raw.dropna(subset=['c_duration'])
        if not duration_data.empty:
            duration_avg = _calc_avg_and_chg(
                duration_data, 'c_fd_code', ['c_duration']
            )
            duration_df = _label_duration_style(duration_avg)
        else:
            duration_df = pd.DataFrame()
    else:
        duration_df = pd.DataFrame()

    # 组装结果
    result = _build_result(bond_type_df, leverage_df, credit_df, duration_df,
                           report_date)
    logger.info(f"生成 {len(result)} 条标签记录")

    # 写入
    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_tag_bd_style', result)

    logger.info("写入完成")
    return result


if __name__ == '__main__':
    from utils.common import should_run, ReportFreq
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
        if ok:
            run(report_date)
    else:
        # 历史補数：2016-12-31 起，37 期季度
        for dt in generate_report_dates('2025-12-31', 37):
            run(dt)
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author: jijunye
@file: tb_fd_tag_asset.py
@time: 2025/12/1 17:16
@description:
基金资产配置标签生成模块

生成三类基金的资产配置标签：
- 权益基金 (001)
- 固收+基金 (002)
- 混合基金 (004)
"""
import sys
from pathlib import Path

def _setup_path():
    """兼容本地和DS环境的路径适配"""
    # 1. 本地开发：从 __file__ 向上找
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return

    # 2. DS环境：资源目录固定路径
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return

    raise RuntimeError("找不到 utils 目录，请检查路径配置")

_setup_path()

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

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
# 配置类
# ============================================================
@dataclass(frozen=True)
class TagConfig:
    """标签配置参数"""
    # 回溯期数
    BACKTRACK_PERIODS: int = 8

    # 权益基金阈值
    EQ_STK_POS_HIGH: float = 90.0  # 区分高仓位与中高仓位阈值

    # 固收+基金阈值
    FI_RISK_LOW: float = 15.0  # 稳健型阈值
    FI_RISK_HIGH: float = 25.0  # 激进型阈值
    FI_CB_STK_RATIO_LOW: float = 1.0  # 股票为主阈值
    FI_CB_STK_RATIO_HIGH: float = 4.0  # 转债为主阈值

    # 混合基金阈值
    MIX_BD_STK_RATIO_LOW: float = 0.5  # 偏股阈值
    MIX_BD_STK_RATIO_HIGH: float = 2.0  # 偏债阈值
    MIX_CB_STK_RATIO_LOW: float = 1.0  # 偏股票阈值
    MIX_CB_STK_RATIO_HIGH: float = 4.0  # 偏转债阈值

    # 择时阈值
    TIMING_STK: float = 5.0  # 股票择时阈值
    TIMING_CB: float = 10.0  # 转债择时阈值
    TIMING_EQ: float = 5.0  # 权益择时阈值


CONFIG = TagConfig()
# ============================================================
# 基类
# ============================================================
class BaseFundTagAsset(ABC):
    """基金资产配置标签基类"""

    # 子类需定义的类属性
    FUND_TYPE_CODE: str = ""  # 基金类型代码
    FUND_TYPE_NAME: str = ""  # 基金类型名称

    def __init__(self, end_date: str):
        """
        初始化

        Args:
            end_date: 报告期，格式 'YYYY-MM-DD'
        """
        self.end_date = end_date
        self.report_dates: List[str] = []
        self.fund_codes: List[str] = []
        self.allocation_df: Optional[pd.DataFrame] = None
        self.result_df: Optional[pd.DataFrame] = None

        self._initialize()

    def _initialize(self):
        """初始化数据"""
        # 生成回溯报告期
        self.report_dates = generate_report_dates(
            self.end_date,
            CONFIG.BACKTRACK_PERIODS
        )

        # 查询基金代码
        self.fund_codes = self._query_fund_codes()
        if not self.fund_codes:
            raise ValueError(f"未找到{self.FUND_TYPE_NAME}基金")

        # 查询资产配置数据
        self.allocation_df = self._query_allocation_data()
        if self.allocation_df.empty:
            raise ValueError("未查询到资产配置数据")

    def _query_fund_codes(self) -> List[str]:
        """查询基金代码列表"""
        sql = f"""
        SELECT c_fd_code
        FROM tytdata.tb_fd_category
        WHERE c_type1_code = :fund_type
          AND c_report_date = :end_date
        """
        with DorisConnector(ENV) as doris:
            df = doris.query(sql, fund_type=self.FUND_TYPE_CODE,
                             end_date=self.end_date)
        return df['c_fd_code'].tolist() if not df.empty else []

    def _query_allocation_data(self, batch_size: int = 500) -> pd.DataFrame:
        """
        查询资产配置数据（分批查询，按报告期去重）

        Args:
            batch_size: 每批查询的基金数量，默认500

        Returns:
            资产配置DataFrame
        """
        # 分批查询
        result_dfs = []

        for i in range(0, len(self.fund_codes), batch_size):
            batch_codes = self.fund_codes[i:i + batch_size]

            sql = f"""
            WITH ranked_data AS (
                SELECT
                    c_fd_code,
                    c_report_date,
                    IFNULL(c_stk_total_ratio, 0) AS c_stk_total_ratio,
                    IFNULL(c_bd_total_ratio, 0) AS c_bd_total_ratio,
                    IFNULL(c_bd_convertible_ratio, 0) AS c_bd_convertible_ratio,
                    IFNULL(c_stk_total_ratio, 0) + IFNULL(c_bd_convertible_ratio, 0) * 0.5 AS c_eq_ratio,
                    ROW_NUMBER() OVER (
                        PARTITION BY c_fd_code, c_report_date
                        ORDER BY c_style
                    ) AS rn
                FROM tytdata.tb_fd_asset_allocation
                WHERE c_fd_code IN (:code_list)
                  AND c_report_date = :report_date
            )
            SELECT 
                c_fd_code, 
                c_report_date, 
                c_stk_total_ratio, 
                c_bd_total_ratio,
                c_bd_convertible_ratio, 
                c_eq_ratio
            FROM ranked_data
            WHERE rn = 1
            """
            with DorisConnector(ENV) as doris:
                for report_dt in self.report_dates:
                    batch_df = doris.query_batch(sql, code_list=batch_codes, report_date=report_dt)
                    if not batch_df.empty:
                        result_dfs.append(batch_df)

        # 合并结果
        if not result_dfs:
            return pd.DataFrame()

        df: pd.DataFrame = pd.concat(result_dfs, ignore_index=True)

        # 转换日期格式
        df['c_report_date'] = pd.to_datetime(df['c_report_date'])

        return df

    def _calc_position_avg(self, group_col: str, value_col: str) -> pd.Series:
        """计算仓位均值"""
        return self.allocation_df.groupby(group_col)[value_col].mean()

    def _calc_position_change_avg(self, group_col: str, value_col: str) -> pd.Series:
        """计算仓位变动均值"""
        sorted_df = self.allocation_df.sort_values([group_col, 'c_report_date'])
        sorted_df['_change'] = sorted_df.groupby(group_col)[value_col].diff()
        sorted_df['_change'] = sorted_df['_change'].abs()
        return sorted_df.groupby(group_col)['_change'].mean()

    @abstractmethod
    def generate(self) -> pd.DataFrame:
        """生成标签，子类实现"""
        pass


# ============================================================
# 权益基金子类
# ============================================================
class EquityFundTagAsset(BaseFundTagAsset):
    """权益基金资产配置标签"""

    FUND_TYPE_CODE = "001"
    FUND_TYPE_NAME = "权益"

    def _query_fund_codes(self) -> List[str]:
        """查询基金代码列表，权益基金仅考虑主动型"""
        sql = f"""
        SELECT c_fd_code
        FROM tytdata.tb_fd_category
        WHERE c_type2_code = :fund_type
          AND c_report_date = :end_date
        """
        with DorisConnector(ENV) as doris:
            df = doris.query(sql, fund_type='001001',
                             end_date=self.end_date)
        return df['c_fd_code'].tolist() if not df.empty else []

    def generate(self) -> pd.DataFrame:
        """生成权益基金资产配置标签"""
        # 计算原始值
        stk_pos_avg = self._calc_position_avg('c_fd_code', 'c_stk_total_ratio')
        stk_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_stk_total_ratio')

        # 构建结果DataFrame
        result = pd.DataFrame({
            'c_fd_code': stk_pos_avg.index,
            'c_report_date': self.end_date,
            'c_stk_pos_avg': stk_pos_avg.values,
            'c_stk_pos_chg_avg': stk_pos_chg_avg.values,
        })

        # 生成标签：股票仓位高低
        result['c_stk_pos_level'] = np.where(
            result['c_stk_pos_avg'] >= CONFIG.EQ_STK_POS_HIGH,
            '高仓位',
            '中高仓位'
        )

        # 生成标签：股票择时
        result['c_stk_timing'] = np.where(
            result['c_stk_pos_chg_avg'] >= CONFIG.TIMING_STK,
            '择时',
            '不择时'
        )

        self.result_df = result
        return result


# ============================================================
# 固收+基金子类
# ============================================================
class FixedIncomePlusFundTagAsset(BaseFundTagAsset):
    """固收+基金资产配置标签"""

    FUND_TYPE_CODE = "002"
    FUND_TYPE_NAME = "固收+"

    def generate(self) -> pd.DataFrame:
        """生成固收+基金资产配置标签"""
        # 计算原始值
        stk_pos_avg = self._calc_position_avg('c_fd_code', 'c_stk_total_ratio')
        cb_pos_avg = self._calc_position_avg('c_fd_code', 'c_bd_convertible_ratio')
        eq_pos_avg = self._calc_position_avg('c_fd_code', 'c_eq_ratio')

        stk_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_stk_total_ratio')
        cb_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_bd_convertible_ratio')

        # 构建结果DataFrame
        result = pd.DataFrame({
            'c_fd_code': stk_pos_avg.index,
            'c_report_date': self.end_date,
            'c_stk_pos_avg': stk_pos_avg.values,
            'c_cb_pos_avg': cb_pos_avg.values,
            'c_eq_pos_avg': eq_pos_avg.values,
            'c_stk_pos_chg_avg': stk_pos_chg_avg.values,
            'c_cb_pos_chg_avg': cb_pos_chg_avg.values,
        })

        # 生成标签：权益风险特征
        result['c_eq_risk_level'] = np.select(
            [
                result['c_eq_pos_avg'] < CONFIG.FI_RISK_LOW,
                result['c_eq_pos_avg'] < CONFIG.FI_RISK_HIGH
            ],
            ['稳健', '均衡'],
            default='激进'
        )

        # 生成标签：股票转债配置策略
        # 计算转债/股票比值，股票为0时设为100
        cb_stk_ratio = np.where(
            result['c_stk_pos_avg'] > 0,
            result['c_cb_pos_avg'] / result['c_stk_pos_avg'],
            100.0  # 股票为0时，视为纯转债
        )

        result['c_stk_cb_strategy'] = np.select(
            [
                result['c_cb_pos_avg'] == 0,  # 无转债
                cb_stk_ratio < CONFIG.FI_CB_STK_RATIO_LOW,  # 转债<股票
                cb_stk_ratio > CONFIG.FI_CB_STK_RATIO_HIGH,  # 转债>4倍股票
            ],
            ['纯股票', '股票为主转债为辅', '转债为主股票为辅'],
            default='股票转债均衡'
        )

        # 生成标签：择时
        result['c_stk_timing'] = np.where(
            result['c_stk_pos_chg_avg'] >= CONFIG.TIMING_STK,
            '择时',
            '不择时'
        )
        result['c_cb_timing'] = np.where(
            result['c_cb_pos_chg_avg'] >= CONFIG.TIMING_CB,
            '择时',
            '不择时'
        )

        self.result_df = result
        return result


# ============================================================
# 混合基金子类
# ============================================================
class MixedFundTagAsset(BaseFundTagAsset):
    """混合基金资产配置标签"""

    FUND_TYPE_CODE = "004"
    FUND_TYPE_NAME = "混合"

    def generate(self) -> pd.DataFrame:
        """生成混合基金资产配置标签"""
        # 计算原始值
        stk_pos_avg = self._calc_position_avg('c_fd_code', 'c_stk_total_ratio')
        cb_pos_avg = self._calc_position_avg('c_fd_code', 'c_bd_convertible_ratio')
        eq_pos_avg = self._calc_position_avg('c_fd_code', 'c_eq_ratio')
        bd_pos_avg = self._calc_position_avg('c_fd_code', 'c_bd_total_ratio')

        stk_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_stk_total_ratio')
        cb_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_bd_convertible_ratio')
        eq_pos_chg_avg = self._calc_position_change_avg('c_fd_code', 'c_eq_ratio')

        # 构建结果DataFrame
        result = pd.DataFrame({
            'c_fd_code': stk_pos_avg.index,
            'c_report_date': self.end_date,
            'c_stk_pos_avg': stk_pos_avg.values,
            'c_cb_pos_avg': cb_pos_avg.values,
            'c_eq_pos_avg': eq_pos_avg.values,
            'c_bd_pos_avg': bd_pos_avg.values,
            'c_stk_pos_chg_avg': stk_pos_chg_avg.values,
            'c_cb_pos_chg_avg': cb_pos_chg_avg.values,
            'c_eq_pos_chg_avg': eq_pos_chg_avg.values,
        })

        # 生成标签：股债配置偏好
        # 计算债券/股票比值，股票为0时设为100
        bd_stk_ratio = np.where(
            result['c_stk_pos_avg'] > 0,
            result['c_bd_pos_avg'] / result['c_stk_pos_avg'],
            100.0
        )

        result['c_stk_bd_pref'] = np.select(
            [
                bd_stk_ratio < CONFIG.MIX_BD_STK_RATIO_LOW,
                bd_stk_ratio > CONFIG.MIX_BD_STK_RATIO_HIGH,
            ],
            ['偏股', '偏债'],
            default='股债均衡'
        )

        # 生成标签：权益仓位偏好（股票vs转债）
        cb_stk_ratio = np.where(
            result['c_stk_pos_avg'] > 0,
            result['c_cb_pos_avg'] / result['c_stk_pos_avg'],
            100.0
        )

        result['c_eq_strategy'] = np.select(
            [
                result['c_cb_pos_avg'] == 0,  # 无转债
                cb_stk_ratio < CONFIG.MIX_CB_STK_RATIO_LOW,
                cb_stk_ratio > CONFIG.MIX_CB_STK_RATIO_HIGH,
            ],
            ['纯股票', '偏股票', '偏转债'],
            default='股票转债均衡'
        )

        # 生成标签：择时
        result['c_eq_timing'] = np.where(
            result['c_eq_pos_chg_avg'] >= CONFIG.TIMING_EQ,
            '择时',
            '不择时'
        )
        result['c_stk_timing'] = np.where(
            result['c_stk_pos_chg_avg'] >= CONFIG.TIMING_STK,
            '择时',
            '不择时'
        )
        result['c_cb_timing'] = np.where(
            result['c_cb_pos_chg_avg'] >= CONFIG.TIMING_CB,
            '择时',
            '不择时'
        )

        self.result_df = result
        return result


# ============================================================
def run(report_date: str):
    """基金资产配置标签生成 - 按季度定期执行

    Args:
        report_date: 报告期，如 '2025-12-31'
    """
    logger.info(f"开始生成 {report_date} 季度的基金资产配置标签")

    # 权益基金标签
    eq_tagger = EquityFundTagAsset(end_date=report_date)
    eq_results = eq_tagger.generate()

    # 固收基金标签
    fi_tagger = FixedIncomePlusFundTagAsset(end_date=report_date)
    fi_results = fi_tagger.generate()

    # 混合基金标签
    mix_tagger = MixedFundTagAsset(end_date=report_date)
    mix_results = mix_tagger.generate()

    # 写入数据库
    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_tag_asset_eq', eq_results)
        doris.insert('tb_fd_tag_asset_fi', fi_results)
        doris.insert('tb_fd_tag_asset_mix', mix_results)

    logger.info(
        f"完成标签生成 - 权益:{len(eq_results)}只 | "
        f"固收:{len(fi_results)}只 | 混合:{len(mix_results)}只"
    )
    return eq_results, fi_results, mix_results


if __name__ == '__main__':
    import sys
    from utils.common import should_run, ReportFreq
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
        if ok:
            run(report_date)
    else:
        # 历史补数：2015-06-30 起，42 期季度
        for dt in generate_report_dates('2025-12-31', 42):
            run(dt)
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author: jijunye
@file: tb_fd_category.py
@time: 2025/11/17 14:32
@description: 需要注意的是,资产配置表格更新后，要对报告期去重
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

import pandas as pd
from datetime import timedelta
from typing import Dict, List, Optional
from utils.common import generate_report_dates
from dataclasses import dataclass
from enum import Enum

from utils.db_connector import DorisConnector
from utils.log import setup_logger
logger = setup_logger(__name__)

# ============================================================
_env = "${db_env}"
ENV = _env if not _env.startswith("${") else "dev"  # 调度注入db_env参数；本地默认dev
# ============================================================

class FundCategory(Enum):
    """基金分类枚举"""
    EQUITY = "001"
    FIXED_INCOME_PLUS = "002"
    BOND = "003"
    MIXED = "004"
    QDII = "005"
    FOF = "006"
    ALTERNATIVE = "007"
    MONEY_MARKET = "008"


@dataclass
class ClassificationResult:
    """分类结果数据类"""
    c_fd_code: str
    class1_code: str
    class1_name: str
    class2_code: str
    class2_name: str

    def to_dict(self) -> Dict[str, str]:
        return {
            'c_fd_code': self.c_fd_code,
            'class1_code': self.class1_code,
            'class1_name': self.class1_name,
            'class2_code': self.class2_code,
            'class2_name': self.class2_name
        }


@dataclass
class ClassifierConfig:
    """分类器配置参数"""
    backtrack_periods: int = 4  # 回溯期数,使用近几期的持仓数据进行分类
    establishment_years: int = 1  # 最低成立年限

    # 权益仓位阈值配置
    active_equity_threshold: float = 70.0  # 主动权益型基金权益仓位阈值，仓位均值大于该数值为权益基金
    mixed_equity_min_threshold: float = 1.0  # 混合债券型基金权益仓位最小值（低于该值认为是债基，高于认为是固收+）
    debt_equity_max_single: float = 40.0  # 偏债/灵活配置权益仓位最大值
    debt_equity_max_avg: float = 30.0  # 偏债/灵活配置权益仓位均值最大值（区分混合基金和固收+）
    bond_enhanced_max: float = 1.0  # 债券增强型权益仓位最大值

    # 可转债阈值配置
    main_convertible_threshold: float = 60.0  # 可转债基金可转债仓位阈值（均值高于该值为可转债基金）


class FundClassifier:
    """基金分类器 - 根据基金基本信息和资产配置数据进行分类"""

    def __init__(self, end_date: str, config: Optional[ClassifierConfig] = None):
        """
        初始化基金分类器

        Parameters:
        end_date: 截面日期，格式 'YYYY-MM-DD'
        config: 分类器配置参数
        """
        self.config = config or ClassifierConfig()
        self.end_date = end_date
        self.report_dts = self._generate_report_dates()
        self.start_date = self.report_dts[0]

        # 缓存属性
        self._fund_info: Optional[pd.DataFrame] = None
        self._asset_allocation: Optional[pd.DataFrame] = None
        self._eligible_funds: Optional[pd.DataFrame] = None
        self._position_metrics: Optional[pd.DataFrame] = None

        # 分类映射字典 - 提取为类属性便于维护
        self._classification_mappings = self._initialize_classification_mappings()

    @property
    def fund_info(self) -> pd.DataFrame:
        """获取基金基本信息"""
        if self._fund_info is None:
            try:
                sql = """
                      SELECT c_fd_code,
                             c_short_name,
                             c_estabdate, 
                             c_transform_date,
                             c_terminate_date,
                             c_class1_code,
                             c_class2_code,
                             c_class3_code
                      FROM tytdata.tb_fd_basic_info 
                      """
                with DorisConnector(ENV) as doris:
                  df = doris.query(sql)

                # 统一处理日期转换
                date_columns = ['c_estabdate', 'c_transform_date', 'c_terminate_date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                df['c_estabdate'] = df['c_estabdate'].where(
                    df['c_transform_date'].isna(),
                    df['c_transform_date']
                )  # 如果发生了转型，则使用转型后的作为新基金的成立日期

                logger.info(f"成功加载基金基本信息: {len(df)} 条记录")
                self._fund_info = df
            except Exception as e:
                logger.error(f"加载基金基本信息失败: {str(e)}")
                raise
        return self._fund_info

    @property
    def asset_allocation(self) -> pd.DataFrame:
        """获取资产配置数据"""
        if self._asset_allocation is None:
            self._asset_allocation = self._load_asset_allocation()
        return self._asset_allocation

    @property
    def eligible_funds(self) -> pd.DataFrame:
        """获取符合条件的基金池"""
        if self._eligible_funds is None:
            self._eligible_funds = self._filter_fund_pool()
        return self._eligible_funds

    @property
    def position_metrics(self) -> pd.DataFrame:
        """获取仓位指标"""
        if self._position_metrics is None:
            self._position_metrics = self._calculate_position_metrics()
        return self._position_metrics

    def _generate_report_dates(self) -> List[str]:
        """生成报告期日期列表"""
        try:
            return generate_report_dates(self.end_date, self.config.backtrack_periods)
        except Exception as e:
            logger.error(f"生成报告期日期失败: {str(e)}")
            raise

    def _load_asset_allocation(self) -> pd.DataFrame:
        """加载资产配置数据"""
        try:
            # language=MySQL
            sql = """
            WITH ranked_data AS (
                SELECT
                    c_fd_code,
                    c_report_date,
                    IFNULL(c_stk_total_ratio, 0) as c_stk_total_ratio,
                    IFNULL(c_bd_convertible_ratio, 0) as c_bd_convertible_ratio,
                    IFNULL(c_stk_total_ratio, 0) + IFNULL(c_bd_convertible_ratio, 0) * 0.5 as c_equity_ratio,
                    ROW_NUMBER() OVER (
                        PARTITION BY c_fd_code, c_report_date
                        ORDER BY c_style
                    ) as rn
                FROM tytdata.tb_fd_asset_allocation
                WHERE c_report_date BETWEEN :start_date AND :end_date 
            )
            SELECT c_fd_code, c_report_date, c_stk_total_ratio, c_bd_convertible_ratio, c_equity_ratio
            FROM ranked_data
            WHERE rn = 1
                  """
            with DorisConnector(ENV) as doris:
                df = doris.query(sql, start_date=self.start_date,
                                 end_date=self.end_date)
            df['c_report_date'] = pd.to_datetime(df['c_report_date'], errors='coerce')

            # 筛选指定报告期数据
            report_dates = pd.to_datetime(self.report_dts)
            filtered_df = df[df['c_report_date'].isin(report_dates)]

            logger.info(f"成功加载资产配置数据: {len(filtered_df)} 条记录")
            return filtered_df
        except Exception as e:
            logger.error(f"加载资产配置数据失败: {str(e)}")
            raise

    def _filter_fund_pool(self) -> pd.DataFrame:
        """筛选符合条件的基金池"""
        try:
            # 成立满一定年限
            establishment_threshold = (
                    pd.to_datetime(self.end_date) -
                    timedelta(days=self.config.establishment_years * 365)
            )

            # 获取该报告期有披露的基金
            disclosed_funds = self.asset_allocation[
                self.asset_allocation['c_report_date'] == self.end_date
                ]['c_fd_code'].unique()

            conditions = [
                self.fund_info['c_fd_code'].isin(disclosed_funds),  # 新增:该期有披露
                self.fund_info['c_estabdate'] <= establishment_threshold,
                self.fund_info['c_terminate_date'].isna() |
                (self.fund_info['c_terminate_date'] > pd.to_datetime(self.end_date))
            ]

            # 合并所有条件
            mask = pd.concat(conditions, axis=1).all(axis=1)
            eligible = self.fund_info[mask].copy()

            logger.info(f"基金池筛选完成: {len(eligible)} 只基金符合条件")
            return eligible
        except Exception as e:
            logger.error(f"基金池筛选失败: {str(e)}")
            raise

    def _calculate_position_metrics(self) -> pd.DataFrame:
        """计算近期仓位相关指标"""
        try:
            # 筛选符合条件的基金
            eligible_codes = self.eligible_funds['c_fd_code'].unique()
            asset_data = self.asset_allocation[
                self.asset_allocation['c_fd_code'].isin(eligible_codes)
            ]

            # 使用groupby一次性计算所有指标
            metrics = asset_data.groupby('c_fd_code').agg({
                'c_equity_ratio': ['mean', 'max'],
                'c_bd_convertible_ratio': 'mean',
                'c_fd_code': 'count'  # 计算期数
            }).round(4)

            # 重命名列
            metrics.columns = [
                'avg_equity_ratio', 'max_equity_ratio',
                'avg_convertible_ratio', 'period_count'
            ]
            metrics = metrics.reset_index()

            logger.info(f"仓位指标计算完成: {len(metrics)} 只基金")
            return metrics
        except Exception as e:
            logger.error(f"仓位指标计算失败: {str(e)}")
            raise

    @staticmethod
    def _initialize_classification_mappings() -> Dict[str, Dict]:
        """初始化分类映射字典"""
        return {
            'class2_mapping': {
                "005001": ("005", "QDII基金", "005001", "QDII股票型基金"),
                "005002": ("005", "QDII基金", "005002", "QDII混合型基金"),
                "005003": ("005", "QDII基金", "005003", "QDII债券型基金"),
                "005004": ("005", "QDII基金", "005004", "QDII-FOF"),
                "006001": ("006", "FOF基金", "006001", "股票型FOF"),
                "006002": ("006", "FOF基金", "006002", "混合型FOF"),
                "006003": ("006", "FOF基金", "006003", "混合型FOF"),
                "006006": ("006", "FOF基金", "006004", "其他FOF"),
                "007001": ("007", "另类投资基金", "007001", "基础设施REITs"),
                "007002": ("007", "另类投资基金", "007002", "商品型基金"),
                "007003": ("007", "另类投资基金", "007003", "量化对冲基金"),
                "004001": ("008", "货币型基金", "008001", "传统货币型基金"),
                "004002": ("008", "货币型基金", "008002", "浮动净值型货币基金")
            },
            'class3_mapping': {
                "005005001": ("005", "QDII基金", "005005", "QDII商品型基金"),
                "005005002": ("005", "QDII基金", "005006", "QDII-REITs"),
            },
            'mixed_fund_mapping': {
                "002001": ("004001", "偏股混合型基金"),
                "002002": ("004002", "平衡混合型基金"),
                "002003": ("004003", "偏债混合型基金"),
                "002004": ("004004", "灵活配置型基金"),
            }
        }

    def classify_funds(self) -> pd.DataFrame:
        """
        执行基金分类

        Returns:
        分类结果DataFrame
        """
        try:
            # 合并基金信息和仓位指标
            fund_data = self.eligible_funds.merge(
                self.position_metrics,
                on='c_fd_code',
                how='left'
            )

            # 执行分类
            results = []
            for _, fund in fund_data.iterrows():
                classification = self._classify_single_fund(fund)
                if classification:
                    results.append(classification.to_dict())

            result_df = pd.DataFrame(results)
            logger.info(f"基金分类完成: {len(result_df)} 只基金完成分类")
            return result_df
        except Exception as e:
            logger.error(f"基金分类执行失败: {str(e)}")
            raise

    def _classify_single_fund(self, fund: pd.Series) -> Optional[ClassificationResult]:
        """对单只基金进行分类"""
        # 按优先级顺序进行分类
        classification_methods = [
            lambda f: self._classify_equity_fund(f),
            lambda f: self._classify_fixed_income_plus(f),
            lambda f: self._classify_bond_fund(f),
            lambda f: self._classify_mixed_fund(f),
            lambda f: self._classify_other_fund(f)
        ]

        for method in classification_methods:
            result = method(fund)
            if result:
                return result

        return None

    def _classify_equity_fund(self, fund: pd.Series) -> Optional[ClassificationResult]:
        """分类权益基金 - 001"""
        # 指数增强型基金
        if fund['c_class3_code'] == "001002002":
            return ClassificationResult(
                fund['c_fd_code'], '001', '权益基金', '001002', '指数增强型基金'
            )

        # 被动指数型基金
        if fund['c_class3_code'] == "001002001":
            return ClassificationResult(
                fund['c_fd_code'], '001', '权益基金', '001003', '被动指数型基金'
            )

        # 主动权益型基金
        if self._is_active_equity_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '001', '权益基金', '001001', '主动权益型基金'
            )

        return None

    def _classify_fixed_income_plus(self, fund: pd.Series) -> Optional[ClassificationResult]:
        """分类固收加基金 - 002"""
        # 可转债基金
        if self._is_convertible_bond_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '002', '固收加基金', '002001', '可转债基金'
            )

        # 混合债券型基金
        if self._is_mixed_bond_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '002', '固收加基金', '002002', '混合债券型基金'
            )

        # 偏债混合型基金
        if self._is_debt_biased_mixed_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '002', '固收加基金', '002003', '偏债混合型基金'
            )

        # 灵活配置型基金
        if self._is_flexible_allocation_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '002', '固收加基金', '002004', '灵活配置型基金'
            )

        return None

    def _classify_bond_fund(self, fund: pd.Series) -> Optional[ClassificationResult]:
        """分类债券型基金 - 003"""
        # 短期纯债型基金
        if fund['c_class3_code'] == "003001002":
            return ClassificationResult(
                fund['c_fd_code'], '003', '债券型基金', '003001', '短期纯债型基金'
            )

        # 中长期纯债型基金
        if fund['c_class3_code'] == "003001001":
            return ClassificationResult(
                fund['c_fd_code'], '003', '债券型基金', '003002', '中长期纯债型基金'
            )

        # 指数型债券基金
        if fund['c_class2_code'] == "003003":
            return ClassificationResult(
                fund['c_fd_code'], '003', '债券型基金', '003003', '指数型债券基金'
            )

        # 债券增强型基金
        if self._is_bond_enhanced_fund(fund):
            return ClassificationResult(
                fund['c_fd_code'], '003', '债券型基金', '003004', '债券增强型基金'
            )

        return None

    def _classify_mixed_fund(self, fund: pd.Series) -> Optional[ClassificationResult]:
        """分类混合型基金 - 004（剩余基金）"""
        if fund["c_class1_code"] != "002":
            return None

        mapping = self._classification_mappings['mixed_fund_mapping']
        class2_code, class2_name = mapping.get(
            fund['c_class2_code'],
            ('004005', '其他混合型基金')
        )

        return ClassificationResult(
            fund['c_fd_code'], '004', '混合型基金', class2_code, class2_name
        )

    def _classify_other_fund(self, fund: pd.Series) -> ClassificationResult:
        """分类其他类型基金"""
        class2_mapping = self._classification_mappings['class2_mapping']
        class3_mapping = self._classification_mappings['class3_mapping']

        # 优先检查二级代码
        if fund["c_class2_code"] in class2_mapping:
            class1_code, class1_name, class2_code, class2_name = class2_mapping[fund["c_class2_code"]]
        # 再检查三级代码
        elif fund["c_class3_code"] in class3_mapping:
            class1_code, class1_name, class2_code, class2_name = class3_mapping[fund["c_class3_code"]]
        else:
            class1_code, class1_name, class2_code, class2_name = "Null", "Null", "Null", "Null"

        return ClassificationResult(
            fund['c_fd_code'], class1_code, class1_name, class2_code, class2_name
        )

    # 辅助判断方法
    def _is_active_equity_fund(self, fund: pd.Series) -> bool:
        """判断是否为主动权益型基金"""
        return (fund['c_class2_code'] == "001001" or
                (fund['c_class2_code'] in ["002001", "002002", "002004"] and
                 pd.notna(fund.get('avg_equity_ratio')) and
                 fund['avg_equity_ratio'] > self.config.active_equity_threshold))

    def _is_convertible_bond_fund(self, fund: pd.Series) -> bool:
        """判断是否为可转债基金"""
        return ('转债' in str(fund.get('c_short_name', '')) or
                (fund['c_class2_code'] in ["003002", "002004", "002003"] and
                 pd.notna(fund.get('avg_convertible_ratio')) and
                 fund['avg_convertible_ratio'] > self.config.main_convertible_threshold))

    def _is_mixed_bond_fund(self, fund: pd.Series) -> bool:
        """判断是否为混合债券型基金"""
        return (fund['c_class2_code'] == "003002" and
                pd.notna(fund.get('avg_equity_ratio')) and
                fund['avg_equity_ratio'] > self.config.mixed_equity_min_threshold)

    def _is_debt_biased_mixed_fund(self, fund: pd.Series) -> bool:
        """判断是否为偏债混合型基金"""
        return (fund['c_class2_code'] == "002003" and
                self._check_debt_equity_thresholds(fund))

    def _is_flexible_allocation_fund(self, fund: pd.Series) -> bool:
        """判断是否为灵活配置型基金"""
        return (fund['c_class2_code'] == "002004" and
                self._check_debt_equity_thresholds(fund))

    def _is_bond_enhanced_fund(self, fund: pd.Series) -> bool:
        """判断是否为债券增强型基金"""
        return (fund['c_class2_code'] == "003002" and
                pd.notna(fund.get('avg_equity_ratio')) and
                fund['avg_equity_ratio'] <= self.config.mixed_equity_min_threshold)

    def _check_debt_equity_thresholds(self, fund: pd.Series) -> bool:
        """检查偏债基金的权益仓位阈值"""
        max_ratio = fund.get('max_equity_ratio')
        avg_ratio = fund.get('avg_equity_ratio')

        return (pd.notna(max_ratio) and pd.notna(avg_ratio) and
                (max_ratio <= self.config.debt_equity_max_single or
                 avg_ratio <= self.config.debt_equity_max_avg))


def run(report_date: str):
    """基金分类更新 - 按季度定期执行

    Args:
        report_date: 报告期，如 '2025-12-31'
    """
    logger.info(f"开始更新 {report_date} 季度的基金分类")

    # 执行分类
    classifier = FundClassifier(end_date=report_date)
    results = classifier.classify_funds()

    # 整理结果
    results.columns = ['c_fd_code', 'c_type1_code', 'c_type1_name',
                       'c_type2_code', 'c_type2_name']
    results['c_report_date'] = pd.to_datetime(report_date)

    # 写入数据库
    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_category', results)

    logger.info(f"完成 {len(results)} 只基金的分类更新")
    return results

if __name__ == '__main__':
    from utils.common import should_run, ReportFreq

    # ── 调度模式 ──────────────────────────────────────────
    raw = "${biz_date}"
    calc_date = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
    ok, report_date = should_run(calc_date, ReportFreq.QUARTERLY)
    if ok:
        logger.info(f"触发执行，报告期={report_date}")
        run(report_date)
    else:
        logger.info(f"非披露窗口，跳过（calc_date={calc_date}）")

    # ── 历史补数模式（补数时：注释上面，取消注释下面）──────
    # for report_date in generate_report_dates('2025-12-31', 44):
    #     run(report_date)

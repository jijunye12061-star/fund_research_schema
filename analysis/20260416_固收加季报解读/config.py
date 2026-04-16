"""
固收+基金季报解读 — 公共配置层

使用方式：
    from config import REPORT_DATE, PREV_DATE, OUTPUT_DIR, fetch_fi_universe
"""
from pathlib import Path

import pandas as pd

from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  全局参数
# ══════════════════════════════════════════════════════════════════════════════

REPORT_DATE = '2025-12-31'    # 当期报告期
PREV_DATE   = '2025-09-30'    # 上期报告期
YEAR_START  = '2025-01-01'    # YTD 起始
PERF_DATE   = '2026-04-15'    # 业绩计算截止日（最新交易日）

# 历史趋势回溯（2020年起，每季度）
HIST_DATES = [
    '2020-03-31', '2020-06-30', '2020-09-30', '2020-12-31',
    '2021-03-31', '2021-06-30', '2021-09-30', '2021-12-31',
    '2022-03-31', '2022-06-30', '2022-09-30', '2022-12-31',
    '2023-03-31', '2023-06-30', '2023-09-30', '2023-12-31',
    '2024-03-31', '2024-06-30', '2024-09-30', '2024-12-31',
    '2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31',
]

# 固收+二级分类代码→名称映射（tb_fd_category c_type1_code='002'）
FI_TYPE2_MAP = {
    '002001': '可转债基金',
    '002002': '混合债券型二级债基',
    '002003': '偏债混合型',
    '002004': '灵活配置型（低仓位）',
}

# 近4期季报（含当期，用于持仓对比）
RECENT_4_DATES = ['2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31']

# 输出目录
OUTPUT_DIR = Path(__file__).parent / 'data'
MANUAL_DIR = Path(__file__).parent / 'manual_data'


def date_to_style(date_str: str) -> str:
    """报告期末 → 对应季报 c_style（以季报先到为准，避免 06-30/12-31 重复统计）"""
    return {'03-31': '01', '06-30': '05', '09-30': '03', '12-31': '06'}[date_str[5:]]


# ══════════════════════════════════════════════════════════════════════════════
#  核心公共函数
# ══════════════════════════════════════════════════════════════════════════════

def fetch_fi_universe(doris: DorisConnector, report_date: str) -> pd.DataFrame:
    """
    获取固收+基金宇宙（主代码去重）。

    返回列：
        c_fd_code, c_short_name, c_type2_code, c_type2_name,
        c_company_name, c_mgr_name, c_estabdate
    """
    sql = """
    SELECT
        b.c_fd_code,
        b.c_short_name,
        cat.c_type2_code,
        cat.c_type2_name,
        b.c_company_name,
        b.c_mgr_name,
        b.c_estabdate
    FROM tb_fd_category cat
    JOIN tb_fd_basic_info b ON b.c_fd_code = cat.c_fd_code
    WHERE cat.c_report_date = :report_date
      AND cat.c_type1_code  = '002'
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    ORDER BY b.c_fd_code
    """
    df = doris.query(sql, report_date=report_date)
    logger.info(f"固收+宇宙 [{report_date}]：{len(df)} 只基金")
    return df


def save_excel(sheets: dict, filename: str) -> Path:
    """
    将多个 DataFrame 写入同一 xlsx 文件。

    Args:
        sheets: {sheet_name: DataFrame}
        filename: 文件名，如 'm2_scale.xlsx'

    Returns:
        输出文件路径
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    logger.info(f"已输出 {path}（{len(sheets)} 个 Sheet）")
    return path

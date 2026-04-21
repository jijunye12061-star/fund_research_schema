"""
筛选权益持仓含有色金属+煤炭（行业）+商业航天（概念）的二级债基

输出列：基金代码 | 基金简称 | 基金公司 | 股票总仓位(%) | 有色金属权重(%) | 煤炭权重(%) | 商业航天权重(%) | 合计权重(%)
合计权重 = 三类股票并集去重后的持仓市值占净值比例
"""
from pathlib import Path

import pandas as pd

from utils.db_connector import DorisConnector
from utils.excel_writer import to_client_excel
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

# ── 查询参数 ─────────────────────────────────────────────────────────────────
REPORT_DATE        = '2025-12-31'
SPACE_CONCEPT_CODE = '007356'   # 商业航天概念


def _fetch_universe(doris: DorisConnector) -> pd.DataFrame:
    """二级债基宇宙：主代码去重，成立满6个月且未终止"""
    sql = """
    SELECT c_fd_code, c_short_name, c_company_name
    FROM tytdata.tb_fd_basic_info
    WHERE c_class3_code = '003002002'
      AND c_terminate_date IS NULL
      AND c_estabdate <= DATE_SUB(:report_date, INTERVAL 6 MONTH)
      AND (c_init_code = c_fd_code OR c_init_code IS NULL)
    """
    return doris.query(sql, report_date=REPORT_DATE)


def _fetch_weights(doris: DorisConnector) -> pd.DataFrame:
    """
    按基金聚合三类持仓权重 + 股票总仓位，在 SQL 层一次完成。
    - 权重口径：c_nav_ratio（占净值比，%），每只股票 LEFT JOIN 后只有一条记录，天然去重
    - 股票总仓位：资产配置表年报数据
    """
    sql = """
    SELECT
        p.c_fd_code,
        MAX(a.c_stk_total_ratio)                                                        AS stk_pos,
        SUM(CASE WHEN d.c_param_name = '有色金属' THEN p.c_nav_ratio ELSE 0 END)        AS w_nonferrous,
        SUM(CASE WHEN d.c_param_name = '煤炭'     THEN p.c_nav_ratio ELSE 0 END)        AS w_coal,
        SUM(CASE WHEN sc.c_concept_code IS NOT NULL THEN p.c_nav_ratio ELSE 0 END)      AS w_space,
        SUM(CASE WHEN d.c_param_name IS NOT NULL OR sc.c_concept_code IS NOT NULL
                 THEN p.c_nav_ratio ELSE 0 END)                                         AS w_total
    FROM tytdata.tb_fd_portfolio_stk p
    JOIN tytdata.tb_fd_basic_info b
        ON  b.c_fd_code = p.c_fd_code
        AND b.c_class3_code = '003002002'
        AND b.c_terminate_date IS NULL
        AND b.c_estabdate <= DATE_SUB(:report_date, INTERVAL 6 MONTH)
        AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
    LEFT JOIN tytdata.tb_stk_industry i
        ON  i.c_stk_code   = p.c_stk_code
        AND i.c_trade_date = p.c_report_date
    LEFT JOIN tytdata.tb_dict_params d
        ON  d.c_param_type = '中信行业分类'
        AND d.c_param_code = LEFT(i.c_citic_code, 6)
        AND d.c_param_name IN ('有色金属', '煤炭')
    LEFT JOIN tytdata.tb_stk_concept sc
        ON  sc.c_stk_code     = p.c_stk_code
        AND sc.c_trade_date   = p.c_report_date
        AND sc.c_concept_code = :concept_code
    LEFT JOIN tytdata.tb_fd_asset_allocation a
        ON  a.c_fd_code     = p.c_fd_code
        AND a.c_report_date = p.c_report_date
        AND a.c_style       = '04'
        AND a.c_is_stat     = -1
    WHERE p.c_report_date = :report_date
      AND p.c_style IN ('02', '04')
    GROUP BY p.c_fd_code
    HAVING w_total > 0
    """
    return doris.query(sql, report_date=REPORT_DATE, concept_code=SPACE_CONCEPT_CODE)


def _build_notes() -> pd.DataFrame:
    """备注内容：仅业务逻辑说明，不涉及字段名/表名/数据库术语"""
    return pd.DataFrame([
        ['报告期',        '2025年年报（2025-12-31），使用基金年报全持仓，而非季报前十大重仓'],
        ['基金范围',      '混合债券型二级基金，成立满6个月且正常运营，按基金主代码去重（同一基金不同份额合并为一条）'],
        ['有色金属/煤炭', '按中信一级行业分类，基于A股持仓；港股持仓因行业归属不完整，不计入本项'],
        ['商业航天',      '按市场概念板块分类，基于A股持仓；港股持仓不计入本项'],
        ['权重口径',      '各类股票持仓市值占基金净值总额的比例（%），即持仓规模相对于基金整体规模的占比'],
        ['股票总仓位(%)', '基金股票类资产合计占净值总额的比例（%），包含A股和港股'],
        ['换算口径',      '若需计算占股票仓位的比例，用各类权重除以股票总仓位即可（例：有色金属权重 ÷ 股票总仓位 × 100）'],
        ['合计权重',      '三类股票合并去重后的持仓市值占净值比例；若某只股票同时属于多个类别，仅计算一次'],
        ['港股',          '港股持仓未纳入有色金属、煤炭、商业航天的统计，实际敞口可能略有低估'],
        ['筛选条件',      '三类合计权重大于0即入选，按合计权重由高到低排列'],
    ], columns=['说明项', '内容'])


def run() -> pd.DataFrame:
    with DorisConnector(ENV) as doris:
        universe = _fetch_universe(doris)
        logger.info(f"二级债基宇宙: {len(universe)} 只")

        weights = _fetch_weights(doris)
        logger.info(f"有持仓基金: {len(weights)} 只")

    result = (
        universe
        .merge(weights, on='c_fd_code')
        .rename(columns={
            'c_fd_code':      '基金代码',
            'c_short_name':   '基金简称',
            'c_company_name': '基金公司',
            'stk_pos':        '股票总仓位(%)',
            'w_nonferrous':   '有色金属权重(%)',
            'w_coal':         '煤炭权重(%)',
            'w_space':        '商业航天权重(%)',
            'w_total':        '合计权重(%)',
        })
        [['基金代码','基金简称','基金公司','股票总仓位(%)','有色金属权重(%)','煤炭权重(%)','商业航天权重(%)','合计权重(%)']]
        .sort_values('合计权重(%)', ascending=False)
        .reset_index(drop=True)
    )

    out_path = Path(__file__).parent / 'data' / '二级债基有色煤炭商业航天持仓.xlsx'
    to_client_excel(
        path=out_path,
        result_df=result,
        notes_df=_build_notes(),
        col_widths={'A': 11.18, 'B': 42.73, 'C': 24.36,
                    'D': 16.54, 'E': 18.63, 'F': 14.45, 'G': 18.63, 'H': 14.45},
        num_cols=['D', 'E', 'F', 'G', 'H'],
        result_sheet='持仓筛选结果',
    )
    logger.info(f"共 {len(result)} 只基金，已保存至 {out_path}")
    return result


if __name__ == '__main__':
    run()

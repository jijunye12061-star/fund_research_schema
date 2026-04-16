"""
基金经理变动分析

Sheet 1: 基金经理变动明细（基金维度）— 代码 / 名称 / 开始时间 / 结束时间 / 基金经理
Sheet 2: 基金经理汇总（经理维度）— 经理代码 / 名称 / 公司 / 各类管理数量 / 最长任期 / 最长独立任期
"""
from pathlib import Path

import pandas as pd

from utils.db_connector import DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'


# ── 查询 ─────────────────────────────────────────────────────────


def _fetch_manager_history(doris: DorisConnector) -> pd.DataFrame:
    """股票型/混合型/债券型、未清盘、主代码的全部正式基金经理任职记录"""
    sql = """
    SELECT m.c_fd_code, b.c_short_name, m.c_person_code, m.c_mgr_name,
           m.c_start_date, m.c_end_date, m.c_is_current
    FROM tb_fd_manager m
    JOIN tb_fd_basic_info b ON b.c_fd_code = m.c_fd_code
    WHERE b.c_class1_code IN ('001', '002', '003')
      AND b.c_terminate_date IS NULL
      AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND m.c_post = '基金经理'
    ORDER BY m.c_fd_code, m.c_start_date
    """
    return doris.query(sql)


def _fetch_current_managed(doris: DorisConnector) -> pd.DataFrame:
    """所有在任经理当前管理的基金（主代码、未清盘），含类型信息"""
    sql = """
    SELECT m.c_fd_code, m.c_person_code, m.c_mgr_name,
           b.c_short_name, b.c_company_name, b.c_class1_code,
           m.c_start_date
    FROM tb_fd_manager m
    JOIN tb_fd_basic_info b ON b.c_fd_code = m.c_fd_code
    WHERE (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)
      AND b.c_terminate_date IS NULL
      AND m.c_post = '基金经理'
      AND m.c_is_current = -1
    """
    return doris.query(sql)


def _fetch_latest_category(doris: DorisConnector) -> pd.DataFrame:
    """每只基金最新一期的组内分类"""
    sql = """
    SELECT c_fd_code, c_type1_code, c_type2_code
    FROM tb_fd_category
    WHERE c_report_date = (SELECT MAX(c_report_date) FROM tb_fd_category)
    """
    return doris.query(sql)


# ── Sheet 1：基金经理变动明细 ────────────────────────────────────


def _build_sheet1(df_history: pd.DataFrame) -> pd.DataFrame:
    out = df_history[['c_fd_code', 'c_short_name',
                      'c_start_date', 'c_end_date', 'c_mgr_name']].copy()
    out.columns = ['代码', '名称', '开始时间', '结束时间', '基金经理']

    out['开始时间'] = pd.to_datetime(out['开始时间']).dt.strftime('%Y%m%d')
    out['结束时间'] = pd.to_datetime(out['结束时间']).dt.strftime('%Y%m%d')
    out['结束时间'] = out['结束时间'].fillna('')  # 在任经理留空
    return out


# ── Sheet 2：基金经理汇总 ────────────────────────────────────────


def _build_fund_manager_map(df_history: pd.DataFrame) -> dict:
    """构建 fund -> [(person_code, start, end), ...] 映射，用于独立任期计算"""
    today = pd.Timestamp.now().normalize()
    mapping = {}
    for _, row in df_history.iterrows():
        fd = row['c_fd_code']
        start = pd.to_datetime(row['c_start_date'])
        end = pd.to_datetime(row['c_end_date']) if pd.notna(row['c_end_date']) else today
        mapping.setdefault(fd, []).append((row['c_person_code'], start, end))
    return mapping


def _calc_independent_start(person_code: str, fd_code: str,
                            start: pd.Timestamp, fund_mgr_map: dict) -> pd.Timestamp | None:
    """计算经理在某基金上的独立任期起始日。无独立期返回 None。"""
    today = pd.Timestamp.now().normalize()
    my_end = today  # 仅对在任经理调用

    others = [(s, e) for pc, s, e in fund_mgr_map.get(fd_code, [])
              if pc != person_code]

    # 找所有与我任期重叠的共管经理
    overlap_ends = [e for s_o, e in others if s_o < my_end and e > start]

    if not overlap_ends:
        return start  # 全程独立

    latest = max(overlap_ends)
    if latest >= my_end:
        return None  # 当前仍有共管经理

    return latest  # 共管经理最后一位离任日 = 独立任期起始


def _build_sheet2(df_history: pd.DataFrame,
                  df_current: pd.DataFrame,
                  df_category: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.now().normalize()

    # 合并分类
    df_cur = df_current.merge(df_category, on='c_fd_code', how='left')

    # 限定范围：管理至少一只股票型/混合型/债券型基金的经理
    restricted_codes = set(
        df_cur.loc[df_cur['c_class1_code'].isin(['001', '002', '003']),
                   'c_person_code']
    )

    # 预计算 fund -> managers 映射
    fund_mgr_map = _build_fund_manager_map(df_history)

    # 当前在管且属于限定范围的基金（用于最长任期计算）
    df_cur_restricted = df_cur[df_cur['c_class1_code'].isin(['001', '002', '003'])].copy()
    df_cur_restricted['c_start_date'] = pd.to_datetime(df_cur_restricted['c_start_date'])
    df_cur_restricted['tenure_days'] = (today - df_cur_restricted['c_start_date']).dt.days

    rows = []
    for person_code in restricted_codes:
        mgr_all = df_cur[df_cur['c_person_code'] == person_code]
        mgr_rest = df_cur_restricted[df_cur_restricted['c_person_code'] == person_code]

        name = mgr_all['c_mgr_name'].iloc[0]
        company = mgr_all['c_company_name'].iloc[0]

        # ── 数量统计 ──
        n_active_equity = len(mgr_rest[mgr_rest['c_type2_code'] == '001001'])
        n_equity = len(mgr_rest[mgr_rest['c_type1_code'] == '001'])
        n_equity_plus = len(mgr_rest[mgr_rest['c_type1_code'].isin(['001', '002', '004'])])
        n_total = len(mgr_all)

        # ── 最长任期 ──
        lt_code = lt_name = lt_start = ''
        if not mgr_rest.empty:
            idx = mgr_rest['tenure_days'].idxmax()
            lt_code = mgr_rest.at[idx, 'c_fd_code']
            lt_name = mgr_rest.at[idx, 'c_short_name']
            lt_start = mgr_rest.at[idx, 'c_start_date']

        # ── 最长独立任期 ──
        li_code = li_name = li_start = ''
        best_days = -1
        for _, r in mgr_rest.iterrows():
            ind_start = _calc_independent_start(
                person_code, r['c_fd_code'],
                pd.to_datetime(r['c_start_date']), fund_mgr_map)
            if ind_start is not None:
                days = (today - ind_start).days
                if days > best_days:
                    best_days = days
                    li_code = r['c_fd_code']
                    li_name = r['c_short_name']
                    li_start = ind_start

        # 格式化日期
        lt_start = lt_start.strftime('%Y%m%d') if isinstance(lt_start, pd.Timestamp) else ''
        li_start = li_start.strftime('%Y%m%d') if isinstance(li_start, pd.Timestamp) else ''

        rows.append({
            '基金经理代码': person_code,
            '基金经理名称': name,
            '基金公司': company,
            '管理主动权益基金数量': n_active_equity,
            '管理权益基金数量（含指数指增）': n_equity,
            '管理含权基金总数量': n_equity_plus,
            '管理基金总数量': n_total,
            '最长任期基金代码': lt_code,
            '最长任期基金名称': lt_name,
            '最长任期基金-开始时间': lt_start,
            '最长独立任期基金代码': li_code,
            '最长独立任期基金名称': li_name,
            '最长独立任期基金-开始时间': li_start,
        })

    return pd.DataFrame(rows)


# ── 主流程 ───────────────────────────────────────────────────────


def run():
    with DorisConnector(ENV) as doris:
        df_history = _fetch_manager_history(doris)
        logger.info(f"任职记录: {len(df_history)} 条")
        df_current = _fetch_current_managed(doris)
        logger.info(f"当前在管关系: {len(df_current)} 条")
        df_category = _fetch_latest_category(doris)
        logger.info(f"最新分类: {len(df_category)} 条")

    sheet1 = _build_sheet1(df_history)
    logger.info(f"Sheet1 行数: {len(sheet1)}")

    sheet2 = _build_sheet2(df_history, df_current, df_category)
    logger.info(f"Sheet2 行数: {len(sheet2)}")

    out_path = Path(__file__).parent / 'data' / '基金经理变动分析.xlsx'
    out_path.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        sheet1.to_excel(writer, sheet_name='基金经理变动明细', index=False)
        sheet2.to_excel(writer, sheet_name='基金经理汇总', index=False)
    logger.info(f"已保存至 {out_path}")
    return sheet1, sheet2


if __name__ == '__main__':
    run()

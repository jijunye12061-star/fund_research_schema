"""诊断北交所行在 ETL 各阶段的存活情况。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for parent in Path(__file__).resolve().parents:
    if (parent / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(parent))
        break

import pandas as pd
from utils.db_connector import OracleConnector, DorisConnector
from insert import (
    _query_ipo_placement, _query_stk_info, _query_init_code_map,
    _assign_sell_dates, _query_sell_vwap,
    determine_board, determine_regime, parse_lock_ratio,
    DATA_START, ENV,
)


def count_bse(df: pd.DataFrame, label: str) -> None:
    if 'c_stk_code' in df.columns:
        bse = df[df['c_stk_code'].astype(str).str.startswith('92')]
        print(f"{label}: 总 {len(df)} 行, BSE {len(bse)} 行")
        if len(bse) and len(bse) <= 5:
            print(bse.head().to_string())
    else:
        # raw stage uses c_stk_inner_code; can't filter by stk_code yet
        print(f"{label}: 总 {len(df)} 行 (无 c_stk_code 字段)")


with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
    print("\n=== 1. Oracle 拉取 ===")
    raw = _query_ipo_placement(oracle, '2025-06-01')
    print(f"raw: {len(raw)} 行 (无 c_stk_code, 只有 c_stk_inner_code)")

    print("\n=== 2. 关联股票信息 (stk_info inner join) ===")
    inner_codes = raw['c_stk_inner_code'].unique().tolist()
    stk_info = _query_stk_info(doris, inner_codes)
    df = raw.merge(stk_info, on='c_stk_inner_code', how='inner')
    count_bse(df, '关联后')

    print("\n=== 3. 过滤 list_date >= 2019-01-01 ===")
    df['c_list_date'] = pd.to_datetime(df['c_list_date'])
    df = df[df['c_list_date'] >= DATA_START].copy()
    count_bse(df, '过滤后')

    print("\n=== 4. 匹配主代码 (init_code inner join) ===")
    init_map = _query_init_code_map(doris, df['c_fd_code'].unique().tolist())
    df = df.merge(init_map, on='c_fd_code', how='inner')
    count_bse(df, '匹配后')

    print("\n=== 5. 业务规则 (board/regime/lock_ratio) ===")
    df['c_stk_code'] = df['c_stk_code'].astype(str)
    df['c_board'] = df['c_stk_code'].apply(determine_board)
    list_date_str = df['c_list_date'].dt.strftime('%Y-%m-%d')
    df['c_regime'] = [determine_regime(b, d) for b, d in zip(df['c_board'], list_date_str)]
    print("c_board 分布:")
    print(df['c_board'].value_counts().to_string())
    print("\nbse 行 c_regime 分布:")
    print(df[df['c_board'] == 'bse']['c_regime'].value_counts().to_string())

    df['c_lock_ratio'] = df['lock_text'].apply(parse_lock_ratio)
    df['c_alloc_qty_unlocked'] = df['c_alloc_qty_total'] * (1 - df['c_lock_ratio'])
    df.drop(columns=['lock_text'], inplace=True)

    print("\n=== 6. 确定卖出日 ===")
    df = _assign_sell_dates(df, doris)
    count_bse(df, '_assign_sell_dates 后')
    bse = df[df['c_board'] == 'bse']
    print(f"BSE 行中 c_sell_date 缺失: {bse['c_sell_date'].isna().sum()}")

    print("\n=== 7. dropna(c_sell_date) ===")
    df = df.dropna(subset=['c_sell_date'])
    count_bse(df, 'dropna 后')

    print("\n=== 8. _query_sell_vwap ===")
    df = _query_sell_vwap(df, doris)
    bse = df[df['c_board'] == 'bse']
    print(f"BSE 行 VWAP 命中: {bse['c_sell_vwap'].notna().sum()} / 总 {len(bse)}")
    print(f"BSE 行 VWAP 缺失: {bse['c_sell_vwap'].isna().sum()}")
    if bse['c_sell_vwap'].isna().sum() > 0:
        print("\n缺失 VWAP 的 BSE 样本:")
        miss = bse[bse['c_sell_vwap'].isna()][['c_stk_code', 'c_sell_date']].drop_duplicates()
        print(miss.head(10).to_string())

"""
一键运行所有模块

Usage:
    python analysis/20260416_固收加季报解读/run_all.py
"""
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.log import setup_logger
import m1_market
import m2_scale
import m3_flow
import m4_perf
import m5_holding

logger = setup_logger(__name__)

MODULES = [
    ('模块一：市场环境',   m1_market.run),
    ('模块二：规模变化',   m2_scale.run),
    ('模块三：资金流向',   m3_flow.run),
    ('模块四：业绩表现',   m4_perf.run),
    ('模块五：持仓配置',   m5_holding.run),
]


def main():
    results = {}
    total_start = time.time()

    for name, func in MODULES:
        logger.info(f"\n{'='*60}")
        logger.info(f"开始 {name}")
        t0 = time.time()
        try:
            func()
            elapsed = round(time.time() - t0, 1)
            results[name] = f'OK ({elapsed}s)'
        except Exception:
            results[name] = 'FAILED'
            logger.error(f"{name} 失败：\n{traceback.format_exc()}")

    total_elapsed = round(time.time() - total_start, 1)
    logger.info(f"\n{'='*60}")
    logger.info(f"运行完成（总耗时 {total_elapsed}s）：")
    for name, status in results.items():
        logger.info(f"  {name}: {status}")


if __name__ == '__main__':
    main()

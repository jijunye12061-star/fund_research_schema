"""
统一日志工具 - 供各 insert.py 使用

用法：
    from utils.log import setup_logger, step

    logger = setup_logger(__name__)

    with step(logger, "查询数据"):
        df = oracle.query(sql)
"""
import contextlib
import logging
import time
from typing import Generator

_FMT = '%(asctime)s - %(levelname)s - %(message)s'


def setup_logger(name: str) -> logging.Logger:
    """配置并返回 logger，同时压制 db_connector 的逐查询 INFO 噪音。"""
    logging.basicConfig(level=logging.INFO, format=_FMT)
    logging.getLogger('utils.db_connector').setLevel(logging.WARNING)
    return logging.getLogger(name)


@contextlib.contextmanager
def step(logger: logging.Logger, name: str) -> Generator[None, None, None]:
    """步骤计时器：打印开始/完成和耗时。"""
    logger.info(f"[{name}] 开始")
    t0 = time.perf_counter()
    yield
    logger.info(f"[{name}] 完成 {time.perf_counter() - t0:.1f}s")

"""
Metabase API 查询封装
接口对齐 DorisConnector：query(**params) / query_batch(code_list, **kwargs)

数据库 ID：
  MetabaseConnector.DB_DORIS  = 43  (Doris 测试库，默认)
  MetabaseConnector.DB_ORACLE = 39  (Oracle 投研通)

认证：读环境变量 METABASE_API_KEY
"""
import os
import re
import time
import logging
from typing import List

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_SLOW_QUERY_THRESHOLD = 5.0
_API_URL = 'http://metabase.jg/api/dataset'
_PAGE_SIZE = 2000   # Metabase 单次返回上限


def _timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        if elapsed >= _SLOW_QUERY_THRESHOLD:
            logger.warning(f'慢查询: {func.__name__} 耗时 {elapsed:.2f}s')
        else:
            logger.debug(f'{func.__name__} 耗时: {elapsed:.2f}s')
        return result
    return wrapper


def _build_payload(db_id: int, sql: str, params: dict) -> dict:
    """把 :param_name 风格的 SQL 和参数转成 Metabase API 格式"""
    mb_sql = re.sub(r':([A-Za-z_]\w*)', r'{{\1}}', sql)

    tags = {}
    parameters = []
    for name, value in params.items():
        tags[name] = {
            'id': name,
            'name': name,
            'display-name': name,
            'type': 'text',
        }
        parameters.append({
            'type': 'category',
            'value': str(value),
            'target': ['variable', ['template-tag', name]],
        })

    return {
        'database': db_id,
        'type': 'native',
        'native': {'template-tags': tags, 'query': mb_sql},
        'parameters': parameters,
    }


def _parse_response(resp: requests.Response) -> pd.DataFrame:
    resp.raise_for_status()
    body = resp.json()
    if 'error' in body:
        raise RuntimeError(f"Metabase 查询错误: {body['error']}")
    data = body['data']
    cols = [c['name'] for c in data['cols']]
    return pd.DataFrame(data['rows'], columns=cols)


class MetabaseConnector:
    """Metabase API 连接器，接口对齐 DorisConnector"""

    DB_DORIS  = 43
    DB_ORACLE = 39

    def __init__(self, db_id: int = 43):
        self.db_id = db_id
        api_key = os.environ.get('METABASE_API_KEY')
        if not api_key:
            raise EnvironmentError('环境变量 METABASE_API_KEY 未设置')
        self._headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json',
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def _fetch_page(self, sql: str, params: dict, offset: int) -> pd.DataFrame:
        """执行单页查询，在原 SQL 外层包 LIMIT/OFFSET"""
        paged_sql = f'SELECT * FROM ({sql}) _t LIMIT {_PAGE_SIZE} OFFSET {offset}'
        payload = _build_payload(self.db_id, paged_sql, params)
        resp = requests.post(_API_URL, json=payload, headers=self._headers, timeout=60)
        return _parse_response(resp)

    @_timer
    def query(self, sql: str, **params) -> pd.DataFrame:
        """执行查询，SQL 中用 :param_name 绑定变量。
        自动分页：返回满 2000 行时继续翻页，对调用方透明。

        示例：
            mb.query("SELECT * FROM tb_fd_basic_info WHERE c_fd_code = :code", code='000001')
        """
        pages = []
        offset = 0
        while True:
            df = self._fetch_page(sql, params, offset)
            pages.append(df)
            if len(df) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
            logger.debug(f'翻页: offset={offset}')

        return pd.concat(pages, ignore_index=True) if len(pages) > 1 else pages[0]

    @_timer
    def query_batch(self, sql: str, code_list: List[str],
                    batch_size: int = 400, **kwargs) -> pd.DataFrame:
        """批量 IN 查询，SQL 中代码列表占位符写 IN (:code_list)

        示例：
            mb.query_batch(
                "SELECT * FROM tb_fd_basic_info WHERE c_fd_code IN (:code_list)",
                code_list=['000001', '000003'],
            )
        """
        if not code_list:
            return pd.DataFrame()

        results = []
        batch_count = (len(code_list) + batch_size - 1) // batch_size
        for i, start in enumerate(range(0, len(code_list), batch_size)):
            batch = code_list[start:start + batch_size]
            # 内部工具，代码列表来自受控数据源，直接展开无注入风险
            in_clause = ','.join(f"'{c}'" for c in batch)
            batch_sql = sql.replace('IN (:code_list)', f'IN ({in_clause})')
            results.append(self.query(batch_sql, **kwargs))
            logger.debug(f'批次 {i + 1}/{batch_count} 完成')

        return pd.concat(results, ignore_index=True)

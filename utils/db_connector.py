"""
数据库连接器 - 支持Oracle和Doris
使用上下文管理器模式，自动管理连接生命周期

@Author: 季俊晔
@Project: fund_research_db
"""
import yaml
import time
import logging
import oracledb
import pandas as pd
from pathlib import Path
from typing import Optional, List
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# 初始化Oracle客户端
oracledb.init_oracle_client()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def timer(func):
    """函数执行时间装饰器"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        logger.info(f'{func.__name__} 耗时: {time.time() - start:.2f}s')
        return result
    return wrapper


class ConfigLoader:
    """配置加载器 - 单例模式"""
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, env: str = 'dev') -> dict:
        """加载数据库配置"""
        if self._config is None:
            config_path = Path(__file__).parent.parent / 'config' / 'database.yaml'
            with open(config_path, 'r', encoding='utf-8') as f:
                all_config = yaml.safe_load(f)
            self._config = all_config.get(env, {})
        return self._config


class OracleConnector:
    """Oracle数据库连接器"""

    def __init__(self, env: str = 'dev'):
        config = ConfigLoader().load(env)['oracle']
        self.dsn = f"{config['host']}:{config['port']}/{config['service_name']}"
        self.user = config['username']
        self.password = config['password']
        self.conn = None

    def __enter__(self):
        self.conn = oracledb.connect(
            user=self.user,
            password=self.password,
            dsn=self.dsn
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    @timer
    def query(self, sql: str) -> pd.DataFrame:
        """执行SQL查询"""
        with self.conn.cursor() as cursor:
            cursor.arraysize = 10000
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=columns)
        return df

    @timer
    def query_batch(self, sql: str, code_list: List[str], batch_size: int = 450) -> pd.DataFrame:
        """
        批量查询 - 自动分批处理大量代码列表

        Args:
            sql: SQL语句，代码列表占位符为 IN (:code_list)
            code_list: 代码列表
            batch_size: 每批数量，默认450
        """
        if not code_list:
            return pd.DataFrame()

        all_results = []
        batch_count = (len(code_list) + batch_size - 1) // batch_size

        with self.conn.cursor() as cursor:
            for i, start_idx in enumerate(range(0, len(code_list), batch_size)):
                batch = code_list[start_idx:start_idx + batch_size]

                # 动态生成绑定变量
                batch_sql = sql.replace(
                    "IN (:code_list)",
                    f"IN ({','.join([f':c{j}' for j in range(len(batch))])})"
                )
                bind_vars = {f'c{j}': code for j, code in enumerate(batch)}

                cursor.execute(batch_sql, bind_vars)
                all_results.extend(cursor.fetchall())
                logger.debug(f"批次 {i + 1}/{batch_count} 完成")

            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(all_results, columns=columns)

        return df


class DorisConnector:
    """Doris数据库连接器"""

    def __init__(self, env: str = 'dev'):
        config = ConfigLoader().load(env)['doris']
        self.url = URL.create(
            "mysql+pymysql",
            username=config['username'],
            password=config['password'],
            host=config['host'],
            port=config['port'],
            database=config['database']
        )
        self.engine = None

    def __enter__(self):
        self.engine = create_engine(
            self.url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.engine:
            self.engine.dispose()

    @timer
    def query(self, sql: str, chunksize: Optional[int] = None, **params) -> pd.DataFrame:
        """执行查询，支持绑定变量

        Args:
            sql: SQL语句，使用 :param_name 占位符
            chunksize: 分块大小，用于大数据量查询
            **params: 绑定变量，如 start_date='2024-01-01'
        """
        with self.engine.connect() as conn:
            result = pd.read_sql(text(sql), conn, params=params, chunksize=chunksize)
            if chunksize:
                result = pd.concat(result, ignore_index=True)
        return result

    @timer
    def query_batch(self, sql: str, code_list: List[str], batch_size: int = 400, **kwargs) -> pd.DataFrame:
        """批量查询 - 自动分批处理大量代码列表

        Args:
            sql: SQL语句,代码列表占位符为 IN (:code_list)
            code_list: 代码列表
            batch_size: 每批数量,默认400
            **kwargs: 其他绑定变量,如 start_date='2024-01-01'
        """
        if not code_list:
            return pd.DataFrame()

        all_results = []
        batch_count = (len(code_list) + batch_size - 1) // batch_size

        with self.engine.connect() as conn:
            for i, start_idx in enumerate(range(0, len(code_list), batch_size)):
                batch = code_list[start_idx:start_idx + batch_size]

                # 动态生成绑定变量占位符
                placeholders = ','.join([f':c{j}' for j in range(len(batch))])
                batch_sql = sql.replace('IN (:code_list)', f'IN ({placeholders})')

                # 构建参数字典
                params = {f'c{j}': code for j, code in enumerate(batch)}
                params.update(kwargs)

                # 执行查询
                batch_df = pd.read_sql(text(batch_sql), conn, params=params)
                all_results.append(batch_df)
                logger.debug(f"批次 {i + 1}/{batch_count} 完成")

        return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

    def execute(self, sql: str) -> None:
        """执行DDL/DML语句"""
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()

    @timer
    def insert(self, table_name: str, df: pd.DataFrame, batch_size: int = 8000) -> None:
        """批量插入数据"""
        with self.engine.connect() as conn:
            with conn.begin():
                df.to_sql(
                    name=table_name,
                    con=conn,
                    if_exists='append',
                    index=False,
                    chunksize=batch_size,
                    method='multi'
                )
        logger.info(f"插入完成: {len(df)}行 → {table_name}")

    def upsert(self, table_name: str, df: pd.DataFrame, batch_size: int = 8000) -> None:
        """插入或更新数据 - UNIQUE KEY表自动覆盖"""
        self.insert(table_name, df, batch_size)


if __name__ == '__main__':
    # # 测试Oracle连接
    # with OracleConnector() as oracle:
    #     test_sql = """
    #         SELECT FCODE, SHORTNAME, ESTABDATE
    #         FROM TYTFUND.FUND_JBXX
    #         WHERE ROWNUM <= 10
    #     """
    #     test_result = oracle.query(test_sql)
    #     print(f"Oracle查询: {len(test_result)}行")

    # 测试Doris连接
    with DorisConnector() as doris:
        test_sql = """
        SELECT * FROM tb_fd_basic_info 
            WHERE c_fd_code IN (:code_list)
        """
        result = doris.query_batch(test_sql, code_list=['000001', '000003'])
        print(f"Doris查询: {len(result)}行")
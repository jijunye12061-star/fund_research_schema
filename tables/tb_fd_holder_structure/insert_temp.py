"""
临时全量同步脚本 — tb_fd_holder_structure + tb_fd_holder_top10
⚠️ DBA 完成 Oracle catalog 配置、视图上线后删除此文件及对应物理表

使用前需在 Doris 手动建临时物理表（DDL 见下方注释），然后直接运行：
    python tables/tb_fd_holder_structure/insert_temp.py

建表 DDL（执行一次，上线后 DROP）：

    CREATE TABLE tytdata.tb_fd_holder_structure (
        c_report_date    DATE          NOT NULL,
        c_fd_code        VARCHAR(20)   NOT NULL,
        c_notice_date    DATE,
        c_total_holder   DECIMAL(20,0),
        c_holder_per     DECIMAL(20,4),
        c_inst_share     DECIMAL(24,4),
        c_inst_ratio     DECIMAL(10,4),
        c_retail_share   DECIMAL(24,4),
        c_retail_ratio   DECIMAL(10,4),
        c_employee_share DECIMAL(24,4),
        c_employee_ratio DECIMAL(10,4),
        c_feeder_share   DECIMAL(24,4),
        c_feeder_ratio   DECIMAL(10,4)
    ) ENGINE=OLAP
    UNIQUE KEY(c_report_date, c_fd_code)
    COMMENT '基金持有人结构表（临时物化，视图上线后删除）[机构研究]'
    DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
    PROPERTIES (
        "replication_allocation" = "tag.location.default: 3",
        "storage_format" = "V2",
        "enable_unique_key_merge_on_write" = "true"
    );

    CREATE TABLE tytdata.tb_fd_holder_top10 (
        c_report_date  DATE          NOT NULL,
        c_fd_code      VARCHAR(20)   NOT NULL,
        c_rank         TINYINT       NOT NULL,
        c_style        VARCHAR(20),
        c_holder_name  VARCHAR(300),
        c_holder_type  VARCHAR(30),
        c_hold_share   DECIMAL(24,4),
        c_hold_ratio   DECIMAL(14,6),
        c_notice_date  DATE
    ) ENGINE=OLAP
    UNIQUE KEY(c_report_date, c_fd_code, c_rank)
    COMMENT '基金前十大持有人明细（临时物化，视图上线后删除）[机构研究]'
    DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
    PROPERTIES (
        "replication_allocation" = "tag.location.default: 3",
        "storage_format" = "V2",
        "enable_unique_key_merge_on_write" = "true"
    );
"""
import sys
from pathlib import Path


def _setup_path():
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return
    raise RuntimeError("找不到 utils 目录，请检查路径配置")


_setup_path()

from utils.db_connector import OracleConnector, DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

CHUNK_SIZE = 5000


def sync_holder_structure():
    """全量同步 FUND_HOLDCHANGE → tb_fd_holder_structure"""
    sql = """
        SELECT
            PDATE          AS c_report_date,
            FCODE          AS c_fd_code,
            NOTICEDATE     AS c_notice_date,
            TRUNC(TOTALHOLDER) AS c_total_holder,
            HOLDERPER      AS c_holder_per,
            INSTHOLD       AS c_inst_share,
            PCTINSTHOLD    AS c_inst_ratio,
            PEISONHOLD     AS c_retail_share,
            PCTPEISONHOLD  AS c_retail_ratio,
            EMPLOYEHOLD    AS c_employee_share,
            PCTEMPLOYEHOLD AS c_employee_ratio,
            FUNDHOLD       AS c_feeder_share,
            PCTFUNDHOLD    AS c_feeder_ratio
        FROM TYTFUND.FUND_HOLDCHANGE
        WHERE EISDEL = '0'
    """
    with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
        df = oracle.query(sql)
        logger.info(f"holder_structure: Oracle 取到 {len(df)} 行")

        for i in range(0, len(df), CHUNK_SIZE):
            chunk = df.iloc[i:i + CHUNK_SIZE]
            doris.insert('tb_fd_holder_structure', chunk)
            logger.info(f"holder_structure: 已写入 {min(i + CHUNK_SIZE, len(df))}/{len(df)}")

    logger.info("holder_structure 同步完成")


def sync_holder_top10():
    """全量同步 FUND_HR_HOLDERTOP10 → tb_fd_holder_top10"""
    sql = """
        SELECT
            CHANGEDATE AS c_report_date,
            FUNDCODE   AS c_fd_code,
            RANK       AS c_rank,
            STYLE      AS c_style,
            SNAME      AS c_holder_name,
            HOLDERTYPE AS c_holder_type,
            HOLDFE     AS c_hold_share,
            RATIO      AS c_hold_ratio,
            NOTICEDATE AS c_notice_date
        FROM TYTFUND.FUND_HR_HOLDERTOP10
        WHERE EISDEL = '0'
    """
    with OracleConnector(ENV) as oracle, DorisConnector(ENV) as doris:
        df = oracle.query(sql)
        logger.info(f"holder_top10: Oracle 取到 {len(df)} 行")

        for i in range(0, len(df), CHUNK_SIZE):
            chunk = df.iloc[i:i + CHUNK_SIZE]
            doris.insert('tb_fd_holder_top10', chunk)
            logger.info(f"holder_top10: 已写入 {min(i + CHUNK_SIZE, len(df))}/{len(df)}")

    logger.info("holder_top10 同步完成")


if __name__ == '__main__':
    sync_holder_structure()
    sync_holder_top10()

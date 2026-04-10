"""临时全量同步脚本：FUND_BS_FEXECUTIVE → tytdata.tb_fd_manager
DBA 建好视图后此脚本可废弃。
"""
import sys
import logging
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.db_connector import OracleConnector, DorisConnector
from utils.log import setup_logger

logger = setup_logger(__name__)
ENV = 'dev'

# DBMS_LOB.SUBSTR 截取 CLOB/NCLOB 前 4000 字符，避免 LOB 对象无法序列化
_SQL = """
SELECT
    a.FUNDCODE,
    a.PERSONCODE,
    a.NAME,
    a.POST,
    a.JOBTITLE,
    a.CHANGEDATE,
    a.ENDDATE,
    a.ISPOSITION,
    a.NOTICEDATE,
    a.LEAVEREASON,
    a.SEX,
    a.BIRTHDATE,
    a.EDUCATION,
    a.PATICTERM,
    DBMS_LOB.SUBSTR(a.RESUME, 2000, 1) AS RESUME,
    DBMS_LOB.SUBSTR(a.REMARK, 2000, 1) AS REMARK,
    a.SOURCE
FROM TYTFUND.FUND_BS_FEXECUTIVE a
WHERE a.EISDEL = '0'
"""

_RENAME = {
    'FUNDCODE':     'c_fd_code',
    'PERSONCODE':   'c_person_code',
    'NAME':         'c_mgr_name',
    'POST':         'c_post',
    'JOBTITLE':     'c_job_title',
    'CHANGEDATE':   'c_start_date',
    'ENDDATE':      'c_end_date',
    'ISPOSITION':   'c_is_current',
    'NOTICEDATE':   'c_notice_date',
    'LEAVEREASON':  'c_leave_reason',
    'SEX':          'c_sex',
    'BIRTHDATE':    'c_birth_date',
    'EDUCATION':    'c_education',
    'PATICTERM':    'c_exp_years',
    'RESUME':       'c_resume',
    'REMARK':       'c_remark',
    'SOURCE':       'c_source',
}

_DATE_COLS = ['c_start_date', 'c_end_date', 'c_notice_date', 'c_birth_date']


def _fetch() -> pd.DataFrame:
    with OracleConnector(ENV) as oracle:
        df = oracle.query(_SQL)
    df = df.rename(columns=_RENAME)
    for col in _DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
        df[col] = df[col].where(df[col].notna(), other=None)
    return df


def run() -> None:
    logger.info("开始同步 tb_fd_manager ...")
    df = _fetch()
    logger.info(f"Oracle 拉取 {len(df)} 条")
    with DorisConnector(ENV) as doris:
        doris.insert('tb_fd_manager', df)
    logger.info(f"同步完成: {len(df)} 条 → tytdata.tb_fd_manager")


if __name__ == '__main__':
    run()

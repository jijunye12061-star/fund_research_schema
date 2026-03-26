-- ============================================================
-- 港股股票行业归属表(静态快照)
-- 每只港股一行, 存储当前最新行业归属
-- 申万/中信/港交所: 前6位=一级, 前9位=二级, 12位=三级
-- GICS: 前6位=一级, 前9位=二级, 12位=三级, 15位=四级
-- ============================================================
DROP TABLE IF EXISTS tb_stk_industry_hk;

CREATE TABLE tytdata.tb_stk_industry_hk (
    c_stk_code   VARCHAR(20)  COMMENT '证券代码(港股5位)',
    c_sw_code    VARCHAR(12)  COMMENT '申万行业代码(三级,029前缀)',
    c_citic_code VARCHAR(12)  COMMENT '中信行业代码(三级,407前缀)',
    c_hkex_code  VARCHAR(12)  COMMENT '港交所行业代码(三级,403前缀)',
    c_gics_code  VARCHAR(15)  COMMENT 'GICS行业代码(四级,402前缀)',
    c_updatetime DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_stk_code)
COMMENT '港股股票行业归属表(静态快照)[机构研究]'
DISTRIBUTED BY HASH(c_stk_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
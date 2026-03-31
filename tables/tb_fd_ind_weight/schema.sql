-- ============================================================
-- 基金行业持仓权重表
-- 每只基金每个报告期各中信一级行业的持仓权重
-- 权重 = 行业持仓市值 / 股票投资总市值（含港股，缺失行业归属的忽略）
-- 仅含半年报(02)和年报(04)，季报持仓披露不完整
-- ============================================================
CREATE TABLE tytdata.tb_fd_ind_weight
(
    `c_report_date` DATE          NULL COMMENT '报告日期',
    `c_fd_code`     VARCHAR(20)   NULL COMMENT '基金代码',
    `c_ind_code`    VARCHAR(6)    NULL COMMENT '中信一级行业代码',
    `c_ind_name`    VARCHAR(50)   NULL COMMENT '中信一级行业名称',
    `c_weight`      DECIMAL(8, 4) NULL COMMENT '行业持仓权重(%,占股票投资总市值)',
    `c_updatetime`  DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
    ENGINE = OLAP UNIQUE KEY (c_report_date, c_fd_code, c_ind_code)
COMMENT '基金行业持仓权重表[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 1
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
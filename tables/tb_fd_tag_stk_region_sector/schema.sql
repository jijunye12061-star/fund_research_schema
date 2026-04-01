-- ============================================================
-- 基金股票投资区域/板块特征标签表
-- 区域特征：近8期季报港股占比均值 → A股/均衡/港股
-- 板块特征：近4期半年报六大板块权重均值+变动指标 → 均衡/赛道/轮动
-- ============================================================
CREATE TABLE tytdata.tb_fd_tag_stk_region_sector
(
    c_report_date      DATE           COMMENT '报告期',
    c_fd_code          VARCHAR(20)    COMMENT '基金代码',

    -- 区域特征（近8期季报）
    c_hk_ratio_avg     DECIMAL(10,4)  COMMENT '港股占股票比均值(%,近8期)',
    c_hk_ratio_latest  DECIMAL(10,4)  COMMENT '港股占股票比最新一期(%)',
    c_region_tag       VARCHAR(10)    COMMENT '区域标签:A股/均衡/港股',

    -- 板块特征（近4期半年报均值，%）
    c_sector_cycle     DECIMAL(10,4)  COMMENT '周期板块权重均值(%)',
    c_sector_mfg       DECIMAL(10,4)  COMMENT '中游制造板块权重均值(%)',
    c_sector_tech      DECIMAL(10,4)  COMMENT '科技板块权重均值(%)',
    c_sector_consumer  DECIMAL(10,4)  COMMENT '消费板块权重均值(%)',
    c_sector_pharma    DECIMAL(10,4)  COMMENT '医药板块权重均值(%)',
    c_sector_fin       DECIMAL(10,4)  COMMENT '金融地产板块权重均值(%)',
    c_sector_chg       DECIMAL(10,4)  COMMENT '板块权重变动指标(%,加权平均绝对变化)',
    c_sector_tag       VARCHAR(10)    COMMENT '板块标签:均衡型/赛道型/轮动型',
    c_sector_pref      VARCHAR(20)    COMMENT '板块偏好(赛道型填写,如消费;其余为空)',

    c_updatetime       DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '基金股票投资区域板块特征标签表[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);
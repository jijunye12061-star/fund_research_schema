CREATE TABLE tytdata.tb_fd_tag_stk_portfolio
(
    c_report_date               DATE           COMMENT '报告期',
    c_fd_code                   VARCHAR(20)    COMMENT '基金代码',

    -- 组合构建（集中度）
    c_sector_hhi                DECIMAL(10,4)  COMMENT '板块HHI（六大板块权重平方和，近4期半年报均值，0~1）',
    c_ind_hhi                   DECIMAL(10,4)  COMMENT '行业HHI（中信一级行业权重平方和，近4期半年报均值，0~1）',
    c_ind_top5_ratio            DECIMAL(10,4)  COMMENT '前5大行业权重占比（%，近4期半年报均值）',
    c_ind_concent_rank          DECIMAL(10,4)  COMMENT '行业集中度复合排名（行业HHI排名+top5排名等权，按基金类型，0~1）',
    c_top10_ratio               DECIMAL(10,4)  COMMENT '前10大持股权重占比（%，近8期季报均值）',
    c_sector_concent_tag        VARCHAR(10)    COMMENT '板块集中度标签：集中/均衡/分散',
    c_ind_concent_tag           VARCHAR(10)    COMMENT '行业集中度标签：集中/均衡/分散',
    c_stk_concent_tag           VARCHAR(10)    COMMENT '个股集中度标签：集中/均衡/分散',

    -- 主动管理
    c_active_sector             DECIMAL(10,4)  COMMENT '主动板块配置偏离度（%，vs中证800，近4期半年报均值）',
    c_active_ind                DECIMAL(10,4)  COMMENT '主动行业配置偏离度（%，板块内行业加权，近4期半年报均值）',
    c_active_sector_rank        DECIMAL(10,4)  COMMENT '主动板块偏离百分比排名（按基金类型，0~1）',
    c_active_ind_rank           DECIMAL(10,4)  COMMENT '主动行业偏离百分比排名（按基金类型，0~1）',
    c_active_tag                VARCHAR(20)    COMMENT '主动配置标签：主动配置/主动板块配置/主动行业配置/空',
    c_new_stk_ratio             DECIMAL(10,4)  COMMENT '持股扩新指标（%，T期新增持仓权重，仅半年报期有值）',
    c_new_stk_tag               VARCHAR(10)    COMMENT '持股扩新标签：积极/适中/保守',
    c_crowd_score               DECIMAL(10,4)  COMMENT '全市场抱团度（持仓加权的个股百分位均值，仅半年报有值）',
    c_crowd_internal_score      DECIMAL(10,4)  COMMENT '同公司抱团度（公司内个股排名加权均值，仅半年报有值）',
    c_crowd_tag                 VARCHAR(10)    COMMENT '抱团度标签：高抱团/中抱团/低抱团（全市场+同公司排名等权复合，按基金类型）',

    -- 交易特征
    c_turnover_avg              DECIMAL(10,4)  COMMENT '基金换手率均值（倍，近4期半年报均值）',
    c_turnover_tag              VARCHAR(10)    COMMENT '换手率标签：高换手/中换手/低换手（按基金类型）',
    c_heavy_retain_rate         DECIMAL(10,4)  COMMENT '重仓股留存率均值（%，近8期季报）',
    c_heavy_turnover            DECIMAL(10,4)  COMMENT '重仓股换手率均值（%，近8期季报）',
    c_heavy_hold_period         DECIMAL(10,4)  COMMENT '重仓股持有期均值（期，近8期季报）',
    c_heavy_trade_rank          DECIMAL(10,4)  COMMENT '重仓交易复合排名（按基金类型，0~1）',
    c_heavy_trade_tag           VARCHAR(20)    COMMENT '重仓交易标签：偏长期持有/持有期适中/偏短期交易',

    c_updatetime                DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '基金股票投资组合特征标签表[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

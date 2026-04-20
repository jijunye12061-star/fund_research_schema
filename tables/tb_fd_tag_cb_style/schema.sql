-- ============================================================
-- 固收+基金转债投资风格标签表
-- ============================================================
CREATE TABLE tytdata.tb_fd_tag_cb_style (
    c_report_date DATE COMMENT '报告日期',
    c_fd_code VARCHAR(20) COMMENT '基金代码',

    -- 组合构建（个券/行业/板块集中度，近8期季报均值）
    c_cb_top10_ratio DECIMAL(10,4) COMMENT '前10大转债占CB仓位比例(%)',
    c_cb_hhi DECIMAL(10,6) COMMENT '个券HHI集中度(0~1)',
    c_cb_concent_tag VARCHAR(10) COMMENT '个券集中度标签:集中/均衡/分散',
    c_cb_ind_top5_ratio DECIMAL(10,4) COMMENT '前5大行业转债占比(%)',
    c_cb_ind_hhi DECIMAL(10,6) COMMENT '行业HHI集中度(0~1)',
    c_cb_ind_concent_tag VARCHAR(10) COMMENT '行业集中度标签:集中/均衡/分散',
    c_cb_sector_top1_ratio DECIMAL(10,4) COMMENT '最大板块转债占比(%)',
    c_cb_sector_hhi DECIMAL(10,6) COMMENT '板块HHI集中度(0~1)',
    c_cb_sector_concent_score DECIMAL(10,4) COMMENT '板块集中度复合分位(0~1)',
    c_cb_sector_concent_tag VARCHAR(10) COMMENT '板块集中度标签:集中/均衡/分散',

    -- 板块特征与偏好（近8期季报均值）
    c_cb_sector_cycle DECIMAL(10,4) COMMENT '周期板块转债权重均值(%)',
    c_cb_sector_mfg DECIMAL(10,4) COMMENT '中游制造板块转债权重均值(%)',
    c_cb_sector_tech DECIMAL(10,4) COMMENT '科技板块转债权重均值(%)',
    c_cb_sector_consumer DECIMAL(10,4) COMMENT '消费板块转债权重均值(%)',
    c_cb_sector_pharma DECIMAL(10,4) COMMENT '医药板块转债权重均值(%)',
    c_cb_sector_fin DECIMAL(10,4) COMMENT '金融地产板块转债权重均值(%)',
    c_cb_sector_chg DECIMAL(10,4) COMMENT '板块权重变动指标(%)',
    c_cb_sector_tag VARCHAR(10) COMMENT '板块标签:赛道型/轮动型/均衡型',
    c_cb_sector_pref VARCHAR(20) COMMENT '板块偏好(仅赛道型有值)',

    -- 交易特征（近8期季报）
    c_cb_retain_rate DECIMAL(10,4) COMMENT '转债留存率均值(%)',
    c_cb_turnover_rate DECIMAL(10,4) COMMENT '转债换手率均值(%)',
    c_cb_hold_period DECIMAL(10,4) COMMENT '转债平均持有期数(期)',
    c_cb_trade_score DECIMAL(10,4) COMMENT '交易特征复合分位(0~1，越高越偏长持)',
    c_cb_trade_tag VARCHAR(20) COMMENT '交易标签:长期持有/持有适中/频繁交易',

    -- 转债风格（属性/股性/债性/余额，近8期季报均值，分位基于全市场）
    c_cb_debt_like_ratio DECIMAL(10,4) COMMENT '平底溢价率≤-20%的CB占比(%)',
    c_cb_equity_like_ratio DECIMAL(10,4) COMMENT '平底溢价率≥20%的CB占比(%)',
    c_cb_attr_tag VARCHAR(10) COMMENT '属性标签:偏债/偏股/均衡',
    c_cb_equity_score DECIMAL(10,4) COMMENT '转股溢价率全市场分位加权均值(0~1),越低股性越强',
    c_cb_equity_tag VARCHAR(12) COMMENT '股性标签:股性强/股性中等/股性弱',
    c_cb_bond_score DECIMAL(10,4) COMMENT '纯债溢价率全市场分位加权均值(0~1),越低债性越强',
    c_cb_bond_tag VARCHAR(12) COMMENT '债性标签:债性强/债性中等/债性弱',
    c_cb_balance_score DECIMAL(10,4) COMMENT '余额全市场分位加权均值(0~1)',
    c_cb_balance_tag VARCHAR(10) COMMENT '余额标签:高余额/中余额/低余额',

    -- 正股风格（市值/价值/成长/盈利，近8期季报均值）
    c_stk_mktcap_score DECIMAL(10,4) COMMENT '正股流通市值全市场分位(0~1)',
    c_stk_mktcap_tag VARCHAR(10) COMMENT '市值标签:大盘/中盘/小盘',
    c_stk_value_score DECIMAL(10,4) COMMENT 'Barra VALUE因子加权暴露',
    c_stk_growth_score DECIMAL(10,4) COMMENT 'Barra GROWTH因子加权暴露',
    c_stk_profit_score DECIMAL(10,4) COMMENT 'Barra PROF因子加权暴露',
    c_stk_style_score DECIMAL(10,4) COMMENT '正股风格复合得分(GROWTH-VALUE),正值偏成长',
    c_stk_style_tag VARCHAR(10) COMMENT '正股风格标签:价值/均衡/成长',

    c_updatetime DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '[机构研究] 固收+基金转债投资风格标签表'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

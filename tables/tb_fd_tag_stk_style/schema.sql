-- ============================================================
-- 基金股票量化风格标签表
-- 市值：持仓加权平均流通市值（亿元） → 大盘/中盘/小盘
-- 价值-成长：持仓加权 VALUE/GROWTH z-score → 价值/成长/GARP/均衡
-- 动量/盈利/质量：持仓加权因子 z-score 跨基金分位 → 高/中/低
-- 窗口：近4期半年报（06-30/12-31），分期计算再平均
-- ============================================================
CREATE TABLE tytdata.tb_fd_tag_stk_style
(
    c_report_date      DATE           COMMENT '报告期',
    c_fd_code          VARCHAR(20)    COMMENT '基金代码',

    c_size_score       DECIMAL(10,4)  COMMENT '持仓加权平均流通市值（亿元，近4期半年报均值）',
    c_size_tag         VARCHAR(10)    COMMENT '市值标签：大盘/中盘/小盘',

    c_value_score      DECIMAL(10,4)  COMMENT '持仓加权VALUE z-score均值（近4期半年报）',
    c_growth_score     DECIMAL(10,4)  COMMENT '持仓加权GROWTH z-score均值（近4期半年报）',
    c_vg_tag           VARCHAR(10)    COMMENT '价值成长标签：价值/成长/GARP/均衡',

    c_momentum_score   DECIMAL(10,4)  COMMENT '持仓加权MOMENTUM z-score均值（近4期半年报）',
    c_momentum_tag     VARCHAR(10)    COMMENT '动量标签：高动量/中动量/低动量',

    c_profit_score     DECIMAL(10,4)  COMMENT '持仓加权PROF z-score均值（近4期半年报）',
    c_profit_tag       VARCHAR(10)    COMMENT '盈利标签：高盈利/中盈利/低盈利',

    c_quality_score    DECIMAL(10,4)  COMMENT '持仓加权QUALITY z-score均值（近4期半年报）',
    c_quality_tag      VARCHAR(10)    COMMENT '质量标签：高质量/中质量/低质量',

    c_dividend_score   DECIMAL(10,4)  COMMENT '持仓加权DTOP z-score均值（近4期半年报，股息率因子）',
    c_dividend_tag     VARCHAR(10)    COMMENT '红利标签：高股息/中股息/低股息',

    c_stability_score  DECIMAL(10,4)  COMMENT '风格稳定性分位数（0-100，市值与价值成长std各自非港股同类分位均值）',
    c_stability_tag    VARCHAR(10)    COMMENT '风格稳定性标签：稳定/适中/漂移（港股基金置空）',

    c_updatetime       DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_report_date, c_fd_code)
COMMENT '基金股票量化风格标签表[机构研究]'
DISTRIBUTED BY HASH(c_fd_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

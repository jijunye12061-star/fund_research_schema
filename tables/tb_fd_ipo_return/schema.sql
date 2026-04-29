CREATE TABLE tytdata.tb_fd_ipo_return
(
    c_fd_code              VARCHAR(16)     COMMENT '子份额代码(PLACING_OBJECT_CODE)',
    c_stk_code             VARCHAR(16)     COMMENT '新股6位代码',
    c_init_code            VARCHAR(16)     COMMENT '主代码(冗余,便于聚合)',
    c_stk_inner_code       VARCHAR(20)     COMMENT '股票内码(CPI关联键,10位数字字符串)',
    c_finance_code         VARCHAR(32)     COMMENT 'IPO融资内码(FINANCECODE)',
    c_board                VARCHAR(16)     COMMENT '板块: star/gem/main_sh/main_sz/bse',
    c_regime               VARCHAR(16)     COMMENT '发行制度: registration/approval',
    c_list_date            DATE            COMMENT '上市日',
    c_sell_date            DATE            COMMENT '卖出日(注册制=上市日,核准制=首次开板日)',
    c_issue_price          DECIMAL(10,4)   COMMENT '发行价',
    c_sell_vwap            DECIMAL(10,4)   COMMENT '卖出日成交均价(c_amount/c_volume)',
    c_confirmed_return     DECIMAL(10,6)   COMMENT '确认涨幅=(sell_vwap-issue_price)/issue_price',
    c_alloc_qty_total      DECIMAL(20,2)   COMMENT '总获配数量(股)',
    c_lock_ratio           DECIMAL(6,4)    COMMENT '锁定比例(0/0.10/0.30等)',
    c_alloc_qty_unlocked   DECIMAL(20,2)   COMMENT '无锁定数量=total*(1-lock_ratio)',
    c_pnl_unlocked         DECIMAL(20,4)   COMMENT '无锁定部分浮盈(元)',
    c_net_asset_estimate   DECIMAL(20,4)   COMMENT '规模分母(主代码层面,元)',
    c_net_asset_report_date DATE           COMMENT '规模参考季报报告期(prev_q)',
    c_size_method          VARCHAR(32)     COMMENT '规模估算方法: quarterly_avg/quarterly_ffill',
    c_updatetime           DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
) ENGINE = OLAP
UNIQUE KEY (c_fd_code, c_stk_code)
COMMENT '公募基金IPO打新收益归因表[机构研究]'
DISTRIBUTED BY HASH(c_init_code) BUCKETS 3
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);

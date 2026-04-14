-- ============================================================
-- 权益基金全量标签查询模板
-- 覆盖：产品基本信息 / 资产配置 / 区域板块 / 风格 / 组合特征 / 交易特征
-- 基金范围：001/002/003/004 主代码（可按需过滤）
-- 参数：替换 {report_date} 为目标报告期，如 '2025-12-31'
-- ============================================================
SELECT
    -- ── 产品基本信息 ──────────────────────────────────────────
    b.c_fd_code,
    b.c_short_name                AS c_fd_name,
    b.c_manager_name,                            -- 基金经理（逗号分隔多人）
    -- 基金经理任职年限：Oracle 有原始数据，Doris 尚未存储
    -- 最新规模：temp_fd_scale_from_tytfund 有但为临时表，建议单独建生产表
    cat.c_type1_name,
    cat.c_type2_name,                            -- 投资类型（主动权益/被动指数等）

    -- ── 资产配置特征（001权益型用eq表，004混合型用mix表）────────
    COALESCE(eq.c_stk_pos_level, mix.c_stk_bd_pref)  AS c_pos_level,  -- 仓位中枢
    COALESCE(eq.c_stk_timing,    mix.c_eq_timing)     AS c_timing_tag, -- 是否择时

    -- ── 区域特征 ──────────────────────────────────────────────
    rs.c_region_tag,
    rs.c_hk_ratio_avg,
    rs.c_hk_ratio_latest,

    -- ── 板块特征 ──────────────────────────────────────────────
    rs.c_sector_tag,
    rs.c_sector_pref,
    rs.c_sector_cycle,
    rs.c_sector_mfg,
    rs.c_sector_tech,
    rs.c_sector_consumer,
    rs.c_sector_pharma,
    rs.c_sector_fin,
    rs.c_sector_chg,

    -- ── 风格标签 ──────────────────────────────────────────────
    sty.c_size_tag,
    sty.c_size_score,
    sty.c_vg_tag,
    sty.c_value_score,
    sty.c_growth_score,
    sty.c_momentum_tag,
    sty.c_momentum_score,
    sty.c_profit_tag,
    sty.c_profit_score,
    sty.c_quality_tag,
    sty.c_quality_score,
    sty.c_dividend_tag,
    sty.c_dividend_score,

    -- ── 组合构建 ──────────────────────────────────────────────
    pf.c_sector_concent_tag,                     -- 板块集中度
    pf.c_ind_concent_tag,                        -- 行业集中度
    pf.c_stk_concent_tag,                        -- 个股集中度
    pf.c_sector_hhi,
    pf.c_ind_hhi,
    pf.c_ind_top5_ratio,
    pf.c_top10_ratio,

    -- ── 主动管理 ──────────────────────────────────────────────
    pf.c_active_tag,                             -- 主动配置风格
    pf.c_active_sector,
    pf.c_active_ind,
    pf.c_new_stk_tag,                            -- 持股扩新
    pf.c_crowd_tag,                              -- 持股抱团
    pf.c_crowd_score,

    -- ── 交易特征 ──────────────────────────────────────────────
    pf.c_turnover_tag,                           -- 换手特征
    pf.c_turnover_avg,
    pf.c_heavy_trade_tag,                        -- 重仓持股风格
    pf.c_heavy_retain_rate,
    pf.c_heavy_hold_period,
    pf.c_buy_timing_tag,                         -- 买入特征
    pf.c_sell_timing_tag                         -- 卖出特征

FROM tytdata.tb_fd_category cat
JOIN tytdata.tb_fd_basic_info b
    ON cat.c_fd_code = b.c_fd_code
    AND (b.c_init_code = b.c_fd_code OR b.c_init_code IS NULL)  -- 主代码去重

-- 资产配置标签（按基金类型分别关联）
LEFT JOIN tytdata.tb_fd_tag_asset_eq eq
    ON cat.c_fd_code = eq.c_fd_code
    AND eq.c_report_date = cat.c_report_date
LEFT JOIN tytdata.tb_fd_tag_asset_mix mix
    ON cat.c_fd_code = mix.c_fd_code
    AND mix.c_report_date = cat.c_report_date

-- 区域/板块特征
LEFT JOIN tytdata.tb_fd_tag_stk_region_sector rs
    ON cat.c_fd_code = rs.c_fd_code
    AND rs.c_report_date = cat.c_report_date

-- 风格标签（仅股票型/混合型有意义）
LEFT JOIN tytdata.tb_fd_tag_stk_style sty
    ON cat.c_fd_code = sty.c_fd_code
    AND sty.c_report_date = cat.c_report_date

-- 组合/交易特征（仅主动权益+混合有意义）
LEFT JOIN tytdata.tb_fd_tag_stk_portfolio pf
    ON cat.c_fd_code = pf.c_fd_code
    AND pf.c_report_date = cat.c_report_date

WHERE cat.c_type1_code IN ('001', '002', '003', '004')
  AND cat.c_report_date = '2025-12-31'   -- ← 替换报告期

-- 常用过滤条件（按需取消注释）
-- AND cat.c_type2_code = '001001'        -- 仅主动权益
-- AND rs.c_region_tag = 'A股'            -- 仅A股基金
-- AND sty.c_size_tag IS NOT NULL         -- 仅有风格标签的基金（过滤纯债/货基）

ORDER BY b.c_asset_net DESC NULLS LAST;

# tb_fd_ipo_return — IPO Return Attribution

## 概述
- **KEY**: `(c_fd_code, c_stk_code)`
- **计算频率**: 季度，约 4/22、7/22、10/22、次年 1/22
- **基金范围**: 所有 `tb_fd_basic_info` 中可匹配到 `c_fd_code` 的公募基金（按 `c_init_code` 归并）
- **数据起点**: 2019-01-01（CPI_PLACERESULT 在此之前 PLACING_OBJECT_CODE 空值率过高）
- **依赖表**: Oracle `CPI_ISSUEBASICINFO` + `CPI_PLACERESULT`；Doris `tb_stk_basic_info`、`tb_stk_quote_daily`、`tb_fd_basic_info`、`tb_fd_asset_allocation`

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `c_fd_code` | VARCHAR(16) | 子份额代码（配售对象代码） |
| `c_init_code` | VARCHAR(16) | 主代码（A份额，冗余便于聚合） |
| `c_stk_code` | VARCHAR(16) | 新股 6 位代码 |
| `c_stk_inner_code` | VARCHAR(20) | 股票内码（CPI 关联键，10 位数字字符串） |
| `c_finance_code` | VARCHAR(32) | IPO 融资内码 |
| `c_board` | VARCHAR(16) | 板块：star / gem / main_sh / main_sz / bse |
| `c_regime` | VARCHAR(16) | 发行制度：registration / approval |
| `c_list_date` | DATE | 上市日 |
| `c_sell_date` | DATE | 卖出日（注册制=上市日，核准制=首次开板日） |
| `c_issue_price` | DECIMAL(10,4) | 发行价 |
| `c_sell_vwap` | DECIMAL(10,4) | 卖出日 VWAP = c_amount / c_volume |
| `c_confirmed_return` | DECIMAL(10,6) | 确认涨幅 = (VWAP - 发行价) / 发行价 |
| `c_alloc_qty_total` | DECIMAL(20,2) | 总获配数量（股） |
| `c_lock_ratio` | DECIMAL(6,4) | 锁定比例（0 / 0.10 / 0.30 等） |
| `c_alloc_qty_unlocked` | DECIMAL(20,2) | 无锁定数量 = total × (1 - lock_ratio) |
| `c_pnl_unlocked` | DECIMAL(20,4) | 无锁定部分浮盈 = unlocked × (VWAP - 发行价) |
| `c_net_asset_estimate` | DECIMAL(20,4) | 规模分母（主代码下所有子份额季报净资产均值之和） |
| `c_net_asset_report_date` | DATE | 规模估算参考的季报报告期（前一期） |
| `c_size_method` | VARCHAR(32) | quarterly_avg（前后均值）/ quarterly_ffill（仅前值） |

## 关键计算

### 区间打新收益率（按主代码聚合）
```sql
SELECT c_init_code, SUM(daily_return) AS interval_return
FROM (
    SELECT c_init_code, c_sell_date,
           SUM(c_pnl_unlocked) / MAX(c_net_asset_estimate) AS daily_return
    FROM tytdata.tb_fd_ipo_return
    WHERE c_sell_date BETWEEN :start AND :end
    GROUP BY c_init_code, c_sell_date
) t
GROUP BY c_init_code;
```

### 剥离打新后的日度收益
````sql
WITH daily_ipo AS (
    SELECT c_init_code, c_sell_date,
           SUM(c_pnl_unlocked) / MAX(c_net_asset_estimate) AS ipo_return
    FROM tytdata.tb_fd_ipo_return
    GROUP BY c_init_code, c_sell_date
)
SELECT n.c_fd_code, n.c_trade_date,
       n.c_nav_return - COALESCE(d.ipo_return, 0) AS ex_ipo_return
FROM tb_fd_nav_daily n
LEFT JOIN tb_fd_basic_info b ON b.c_fd_code = n.c_fd_code
LEFT JOIN daily_ipo d
       ON d.c_init_code = b.c_init_code
      AND d.c_sell_date = n.c_trade_date;
````

## 注意事项
- 仅计算无锁定（90%）部分浮盈，不含锁定 10% 部分
- LOCKPERIOD 中 ~2% 脏文本默认 lock_ratio=0，对"剥离打新"方向保守（高估打新收益 → 剥离后净收益偏低）
- c_sell_vwap 缺失（停牌/退市极少）的行被跳过，不影响其他基金
- 北交所 IPO 使用上市首日 VWAP，简化处理

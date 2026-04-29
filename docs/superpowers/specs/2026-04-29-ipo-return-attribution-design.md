# 公募打新收益归因表设计

> 状态：已与用户对齐，待落 plan 实施
> 日期：2026-04-29
> 关联文档：[scripts/daxin.txt](../../../scripts/daxin.txt)（国信研报方法论）、[docs/query/ipo-return-attribution.md](../../query/ipo-return-attribution.md)（数据探查）

## 1. 背景与目标

### 业务目标

把公募基金净值收益中的"网下打新收益"部分剥离出来，用于基金画像、风格归因、绩效解释。当前线上有备用表 `FUND_DR_NSTOCKCTNEW` 提供逐基金 × 新股贡献度，但其计算方法（10 日均价等）过粗、口径不透明，不满足精细化分析需要，因此自建。

### 设计取舍

参考国信研报（[scripts/daxin.txt](../../../scripts/daxin.txt)）和中金研报方法论，**采用中金的简化版**，原因：

1. **不展开日度持仓序列**：研报理论上的日度浮盈累加（上市首日、中间日、卖出日三段公式）行数会到亿级，而打新收益绝大部分集中在卖出日实现，事件级粒度足够。
2. **只算无锁定部分**：90/10 拆分中，10% 锁定 6 个月的部分价值波动复杂、估值规则模糊，且占比小，不计入。
3. **规模分母不用研报的 4 类信号 5 步流程**：那是工业级精度方案，工作量极大；用季报 `c_net_asset` 前后两期均值已能覆盖中小规模打新基金的需求。

### 数据范围

- 时间起点：2019-01-01（CPI_PLACERESULT 在 2019 年起 PLACING_OBJECT_CODE 空值率降至 ~20%，可用）
- 板块覆盖：科创板、创业板、沪深主板、北交所
- 基金范围：所有在 `tb_fd_basic_info` 中能找到 `c_fd_code` 的公募基金（按主代码 `c_init_code` 归并各份额）

## 2. 数据源

| 表 | 位置 | 用途 |
|----|------|------|
| `TYTFUND.CPI_ISSUEBASICINFO` | Oracle | IPO 元信息：FINANCECODE、ISSUEPRICE、SECURITY_INNER_CODE、NOTICEDATE |
| `TYTFUND.CPI_PLACERESULT` | Oracle | 网下配售明细：PLACING_OBJECT_CODE、SHAREPLACE、LOCKPERIOD |
| `tytdata.tb_stk_basic_info` | Doris | 股票上市日、c_stk_code、c_inner_code 关联 |
| `tytdata.tb_stk_quote_daily` | Doris | 日行情：c_close、c_amount、c_volume、c_is_limit_up |
| `tytdata.tb_fd_basic_info` | Doris | 基金主代码归并（c_fd_code → c_init_code） |
| `tytdata.tb_fd_asset_allocation` | Doris | 基金季报 c_net_asset，规模分母 |

**Oracle 过滤条件**：
- `CPI_ISSUEBASICINFO.SECURITYTYPECODE = '058001001' AND FINATYPE = '001'`（A 股首发）
- `CPI_PLACERESULT.PLACEOBJECTTYPE = '网下机构投资者' AND PLACING_OBJECT_CODE IS NOT NULL`

## 3. 表设计

### 3.1 表 `tb_fd_ipo_return`

每次 (基金子份额, 新股) 配售事件 1 行。同时含规模分母字段（同一主代码 × 卖出日下的多个子份额行重复存储），便于下游一次取数完成"事件明细 + 日度收益率"两类查询。

**主键 / UNIQUE KEY**：`(c_fd_code, c_stk_code)`
**分桶键**：`c_init_code`
**分区**：按 `c_sell_date` 月分区

| 字段 | 类型 | 说明 |
|------|------|------|
| `c_fd_code` | VARCHAR(16) | 子份额代码（CPI_PLACERESULT.PLACING_OBJECT_CODE） |
| `c_init_code` | VARCHAR(16) | 主代码（冗余，便于按主代码聚合 / 与其他基金表 join） |
| `c_stk_code` | VARCHAR(16) | 新股 6 位代码 |
| `c_stk_inner_code` | BIGINT | 股票内码（CPI 关联键） |
| `c_finance_code` | VARCHAR(32) | IPO 融资内码（FINANCECODE） |
| `c_board` | VARCHAR(16) | 板块：`star` / `gem` / `main_sh` / `main_sz` / `bse` |
| `c_regime` | VARCHAR(16) | 发行制度：`registration`（注册制）/ `approval`（核准制） |
| `c_list_date` | DATE | 上市日 |
| `c_sell_date` | DATE | 卖出日（注册制 = 上市日；核准制 = 首次开板日） |
| `c_issue_price` | DECIMAL(10,4) | 发行价 |
| `c_sell_vwap` | DECIMAL(10,4) | 卖出日成交均价 = c_amount / c_volume |
| `c_confirmed_return` | DECIMAL(10,6) | 确认涨幅 = (c_sell_vwap - c_issue_price) / c_issue_price |
| `c_alloc_qty_total` | DECIMAL(20,2) | 总获配数量（PLACERESULT.SHAREPLACE） |
| `c_lock_ratio` | DECIMAL(6,4) | 锁定比例（0 / 0.10 / 0.30 等） |
| `c_alloc_qty_unlocked` | DECIMAL(20,2) | 无锁定数量 = c_alloc_qty_total × (1 - c_lock_ratio) |
| `c_pnl_unlocked` | DECIMAL(20,4) | 无锁定部分浮盈 = c_alloc_qty_unlocked × (c_sell_vwap - c_issue_price) |
| `c_net_asset_estimate` | DECIMAL(20,4) | 主代码 × 卖出日的规模分母（同组合下子份额行重复） |
| `c_net_asset_report_date` | DATE | 估算规模的主要参考季报报告期（前后均值时记录 prev_q） |
| `c_size_method` | VARCHAR(32) | 规模估算方法：`quarterly_avg` / `quarterly_ffill` |
| `c_updatetime` | DATETIME(6) | 写入时间，DEFAULT CURRENT_TIMESTAMP(6) |

### 3.2 下游消费

```sql
-- 区间打新收益率（基金主代码层面）
SELECT c_init_code, SUM(daily_return) AS interval_return
FROM (
    SELECT c_init_code, c_sell_date,
           SUM(c_pnl_unlocked) / MAX(c_net_asset_estimate) AS daily_return
    FROM tytdata.tb_fd_ipo_return
    WHERE c_sell_date BETWEEN :start AND :end
    GROUP BY c_init_code, c_sell_date
) t
GROUP BY c_init_code;

-- 单只基金的 IPO 配售明细
SELECT c_fd_code, c_stk_code, c_sell_date, c_pnl_unlocked, c_confirmed_return
FROM tytdata.tb_fd_ipo_return
WHERE c_init_code = :init_code
ORDER BY c_sell_date;

-- 剥离打新后的基金日度收益（视图层 / 临时分析，不固化）
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
```

## 4. ETL 流程

### 4.1 板块与发行制度判定

| 板块 | 代码前缀 | 注册制起始日 | 起始前 c_sell_date | 起始后 c_sell_date |
|------|---------|------------|-------------------|------------------|
| 科创板 | 688 / 689 | 2019-07-22（开市即注册制） | — | 上市日 |
| 创业板 | 300 / 301 | 2020-08-24 | 首次开板日 | 上市日 |
| 沪市主板 | 60 | 2023-04-10 | 首次开板日 | 上市日 |
| 深市主板 | 000 / 001 / 002 / 003 | 2023-04-10 | 首次开板日 | 上市日 |
| 北交所 | 83 / 87 / 92 | 2021-11-15（开市即注册制） | — | 上市日 |

**首次开板日 SQL**：
```sql
SELECT MIN(c_trade_date) AS first_open_date
FROM tytdata.tb_stk_quote_daily
WHERE c_stk_code = :stk_code
  AND c_trade_date >= :list_date
  AND c_is_limit_up = '否'
```

### 4.2 锁定比例解析

`LOCKPERIOD` 是自由文本字段。基于 2019+ 全量探查（≥1500 万行），实测主要分类：

| 类型 | 占比 | 文本特征 | c_lock_ratio |
|------|------|---------|--------------|
| 普通网下（无锁定） | ~57% | "普通网下推荐配售类" / "普通网下追加配售类" / NULL | 0 |
| 90/10 锁定 | ~40% | 含 "10% 的股份锁定 6 个月..." | 0.10 |
| 70/30、60/40 等少量 | ~2% | 含 "30% 的股份锁定..." 等 | X / 100 |
| 异常脏文本 | ~1.8% | 仅 "6个月" / "9个月" 这种孤立文本 | 默认 0（容忍） |

**Python 端解析（不在 SQL 端跑全表正则）**：

```python
import re
LOCK_PAT = re.compile(r'(\d{1,3})\s*%[^,。;]{0,8}股份[^,。;]{0,4}[锁限]')

def parse_lock_ratio(text: str) -> float:
    """从 LOCKPERIOD 文本提取锁定比例。匹配不到默认 0。"""
    if not text:
        return 0.0
    m = LOCK_PAT.search(text)
    if m:
        return int(m.group(1)) / 100
    return 0.0
```

风险：极少数脏文本可能本应有锁定但没匹配上，导致少数样本浮盈被高估。但占比 < 2%，且这些都是异常文本无法判断真实锁定比例，按 0 处理是稳健方向（高估收益对"剥离打新"是保守的，剥离后的净收益偏低）。

### 4.3 规模分母估算

对每行 (c_fd_code, c_stk_code)：

1. 拿到该基金的主代码 `c_init_code` 和卖出日 `c_sell_date`
2. 查 `tb_fd_basic_info` 拿到该主代码下所有的子份额 `c_fd_code` 列表
3. 对每个子份额，找：
   - `prev_q` = `c_sell_date` 之前最近的季报报告期对应的 `c_net_asset`
   - `next_q` = `c_sell_date` 之后最近的季报报告期对应的 `c_net_asset`
4. 该子份额规模：
   - 若 `next_q` 已披露：`(prev_nav + next_nav) / 2`，`c_size_method = 'quarterly_avg'`
   - 若 `next_q` 未披露（c_sell_date 落在最新季报之后）：退化为 `prev_nav`，`c_size_method = 'quarterly_ffill'`
   - 若 `prev_q` 不存在（基金成立未满一季）：跳过该子份额，不参与汇总
5. 主代码层面规模 = SUM(各子份额规模)
6. 把 `c_net_asset_estimate` 写到该 (c_init_code, c_sell_date) 下的所有子份额行（重复存储）

### 4.4 调度

**触发节奏**：每季度跑一次，季报披露后约 4/22、7/22、10/22、次年 1/22（参考 CLAUDE.md 标签表第一轮约定）。

**首次全量初始化（一次性）**：
- 拉 2019-01-01 ~ 当前日期所有 IPO 的配售明细，全部计算并写入。注册制 IPO 的 c_sell_date 即上市日，可直接计算；核准制 IPO 已经全部开板，c_sell_date 也可定。
- 规模分母用截至当前可获取的季报数据计算。最早几期的 c_size_method 可能仍是 `quarterly_avg`（因为前后两期都已披露）。

**增量跑批（每季度）**：
1. **新增事件**：找出 `c_list_date` 落在"上一季报截止日 ~ 本季报截止日"窗口内的新 IPO，加入表
2. **回填**：上一次跑批时核准制 IPO 还没开板（c_sell_date IS NULL）的，本次回填 c_sell_date / c_sell_vwap / c_confirmed_return / c_pnl_unlocked
3. **分母回填**：因为 c_net_asset_estimate 用的是前后两期均值，新一期季报披露后，"上一季报~本季报"窗口内所有行的分母从 ffill 切换到 avg。**只重写本季窗口内的行**（更早季度已 quarterly_avg 完成的不动）。

**insert.py 提供 `--season YYYY-Q?` 参数控制重算窗口；`--init` 参数走首次全量初始化路径**。

## 5. 关键决策记录

1. **不重建日度持仓展开**：每只 IPO 只算"卖出日浮盈"一行（事件级粒度）。
2. **不计算锁定 10% 部分**：业务影响小，但实现复杂度大幅降低。
3. **保留子份额粒度**：因 A/C 份额可能独立打新，且 ETF + 联接基金的归并需要明示，子份额不能丢失。
4. **单表 + 规模分母冗余**：A 表事件级粒度后，没必要再拆一张 B 聚合表。规模分母按子份额行重复存储是轻微反范式，但消费侧 GROUP BY 平凡操作。
5. **分区按 c_sell_date 月分区**：消费侧主要按卖出日过滤区间。
6. **规模分母用季报前后两期均值**：比简单 ffill 更平滑，对季度内规模剧烈变化的基金更友好。
7. **正则只匹配比例数字**：兼容 90/10、70/30、60/40 等多种锁定形态。
8. **仅用上市日 + 注册制改革分界日推断 c_regime**：CPI 没有明确"注册制"标识字段，按规则推断错误率极低。
9. **不写"长期一字板未开板"兜底**：实测无此情况，遇到再加。
10. **不检查基金成立日过滤虚假配售**：先信任源数据，遇到再加。
11. **PLACING_OBJECT_CODE 在 tb_fd_basic_info 不命中的丢弃**：这些是私募 / 机构 / 个人户，58% 占比，但不在公募打新归因范围内。

## 6. 已知风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| LOCKPERIOD 脏文本 ~2% 默认按 0 处理 | 少数样本浮盈被高估 | 高估收益 = 剥离更多 = 净收益偏低，方向保守 |
| 注册制规则推断不能 100% 准确 | 极少跨期上市股票可能误判 | 错误率 << 1%，可接受 |
| CPI_PLACERESULT 2016-2018 完整度差 | 历史样本不全 | 数据起点定在 2019，避开问题区间 |
| 卖出日 VWAP 缺失（停牌 / 退市极少） | c_pnl_unlocked = NULL | 下游聚合时 SKIP，不影响其他基金 |
| 北交所"上市后 5 日不设涨跌幅"特殊性 | 上市首日 VWAP 可能不代表稳态价格 | 简化为上市首日 VWAP，符合中金口径 |
| 规模分母在子份额行重复存储 | 轻微反范式 | 数据量不大（百万级），季度全量重写本季窗口可接受 |

## 7. 落地物料

- `tables/tb_fd_ipo_return/`
  - `schema.sql`：表 DDL
  - `insert.py`：ETL（含板块判定、LOCKPERIOD 解析、卖出日定位、VWAP 取数、浮盈计算、规模分母拼接）
  - `SPEC.md`：业务说明

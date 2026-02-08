# tb_fd_basic_info - 基金基础信息表

## 基本信息

- **主键**: c_fd_code
- **更新频率**: 日度
- **数据范围**: 全市场基金

## 数据来源
- **Oracle表**: 
  - TYTFUND.FUND_JBXX（主表 - 基本信息）
  - TYTFUND.FUND_BS_OFINFO（基金概况）
  - TYTFUND.DIM_FD_INIT_CODE（初始代码）
  - TYTFUND.FUND_BS_ATYPE（定开分类）
  - TYTFUND.FUND_BS_CFINFO（持有期）
- **更新逻辑**: 全量替换（UNIQUE KEY自动覆盖）

## 数据质量
- **特殊映射**: 519997→519996, 519995→519994, 370011→37001B
- **默认规则**: REITs基金自动归类到007（另类投资基金）
- **去重逻辑**: 初始代码按REMOVE_DT倒序取最新记录

## 字段清单

| 字段名                   | 类型            | 注释       | 说明      |
|-----------------------|---------------|----------|---------|
| c_fd_code             | VARCHAR(20)   | 基金代码     | 六位代码    |
| c_short_name          | VARCHAR(100)  | 基金简称     | -       |
| c_full_name           | VARCHAR(200)  | 基金全称     | -       |
| c_estabdate           | DATE          | 成立日期     | 基金成立日   |
| c_terminate_date      | DATE          | 终止日期     | 清盘日期    |
| c_terminate_reason    | VARCHAR(100)  | 终止原因     | -       |
| c_class1_code         | VARCHAR(10)   | 一级分类代码   | 三位代码    |
| c_class1_name         | VARCHAR(50)   | 一级分类名称   | 见枚举值    |
| c_class2_code         | VARCHAR(10)   | 二级分类代码   | 六位代码    |
| c_class2_name         | VARCHAR(50)   | 二级分类名称   | 见枚举值    |
| c_class3_code         | VARCHAR(10)   | 三级分类代码   | 九位代码    |
| c_class3_name         | VARCHAR(50)   | 三级分类名称   | 见枚举值    |
| c_manager_code        | VARCHAR(100)  | 基金经理代码   | 多个用逗号分隔 |
| c_manager_name        | VARCHAR(100)  | 基金经理名称   | 多个用逗号分隔 |
| c_custodian_code      | VARCHAR(50)   | 托管银行代码   | -       |
| c_custodian_name      | VARCHAR(100)  | 托管银行     | -       |
| c_company_code        | VARCHAR(50)   | 基金公司代码   | -       |
| c_company_name        | VARCHAR(100)  | 基金公司简称   | -       |
| c_invest_scope        | TEXT          | 投资范围     | 招募说明书约定 |
| c_invest_standard     | TEXT          | 投资标准     | 资产配置比例  |
| c_purchase_status     | VARCHAR(20)   | 申购状态     | 见枚举值    |
| c_redeem_status       | VARCHAR(20)   | 赎回状态     | 见枚举值    |
| c_fund_nature         | VARCHAR(50)   | 基金性质     | 见枚举值    |
| c_transform_date      | DATE          | 转型生效日期   | 基金转型日   |
| c_regular_open_status | VARCHAR(10)   | 定开情况     | 1是/0否   |
| c_min_hold_period     | DECIMAL(18,2) | 最短持有期    | 单位：月    |
| c_mgmt_fee_rate       | VARCHAR(20)   | 基金管理费率   | -       |
| c_custodian_fee_rate  | VARCHAR(20)   | 基金托管费率   | -       |
| c_sales_fee_rate      | VARCHAR(20)   | 基金销售服务费率 | -       |
| c_init_code           | VARCHAR(20)   | 初始代码     | 初始代码    |
| c_updatetime          | DATETIME(6)   | 更新时间     | 自动更新    |

## 枚举值

### 申购状态 (c_purchase_status)

| 值    | 说明     |
|------|--------|
| 开放申购 | 正常开放申购 |
| 暂停申购 | 暂停申购   |
| 认购期  | 认购期    |
| 场内交易 | 场内交易   |
| 封闭期  | 封闭期    |
| 暂停交易 | 暂停交易   |
| 限大额  | 限制大额申购 |

### 赎回状态 (c_redeem_status)

| 值    | 说明     |
|------|--------|
| 开放赎回 | 正常开放赎回 |
| 暂停赎回 | 暂停赎回   |
| 认购期  | 认购期    |
| 场内交易 | 场内交易   |
| 封闭期  | 封闭期    |
| 暂停交易 | 暂停交易   |

### 基金性质 (c_fund_nature)

| 值      | 说明         |
|--------|------------|
| 证券投资基金 | 普通证券投资基金   |
| FOF    | 基金中基金      |
| 联接基金   | ETF联接基金    |
| MOM    | 管理人中管理人    |
| 集合计划   | 集合资产管理计划   |
| ETF    | 交易型开放式指数基金 |
| LOF    | 上市型开放式基金   |
| REITs  | 不动产投资信托基金  |

### 基金分类 (c_class1/2/3_code)

| 一级分类       | 二级分类               | 三级分类                  |
|------------|--------------------|-----------------------|
| 001 股票型基金  | 001001 普通股票型基金     | 001001001 普通股票型基金     |
|            | 001002 指数型股票基金     | 001002001 被动指数型基金     |
|            |                    | 001002002 增强指数型基金     |
| 002 混合型基金  | 002001 偏股混合型基金     | 002001001 偏股混合型基金     |
|            | 002002 平衡混合型基金     | 002002001 平衡混合型基金     |
|            | 002003 偏债混合型基金     | 002003001 偏债混合型基金     |
|            | 002004 灵活配置型基金     | 002004001 灵活配置型基金     |
|            | 002005 其他混合型基金     | 002005001 其他混合型基金     |
| 003 债券型基金  | 003001 纯债型基金       | 003001001 中长期纯债型基金    |
|            |                    | 003001002 短期纯债型基金     |
|            | 003002 混合债券型基金     | 003002001 混合债券型一级基金   |
|            |                    | 003002002 混合债券型二级基金   |
|            | 003003 指数型债券基金     | 003003001 被动指数型债券基金   |
|            |                    | 003003002 增强指数型债券基金   |
| 004 货币型基金  | 004001 传统货币型基金     | 004001001 传统货币型基金     |
|            | 004002 浮动净值型货币基金   | 004002001 浮动净值型货币基金   |
| 005 QDII基金 | 005001 QDII股票型基金   | 005001001 QDII普通股票型基金 |
|            |                    | 005001002 QDII被动指数型基金 |
|            |                    | 005001003 QDII增强指数型基金 |
|            | 005002 QDII混合型基金   | 005002001 QDII偏股混合型基金 |
|            |                    | 005002002 QDII平衡混合型基金 |
|            |                    | 005002003 QDII偏债混合型基金 |
|            |                    | 005002004 QDII灵活配置型基金 |
|            | 005003 QDII债券型基金   | 005003001 QDII混合债券型基金 |
|            | 005004 QDII-FOF    | 005004001 QDII-FOF    |
|            | 005005 QDII-另类投资基金 | 005005001 QDII商品型基金   |
|            |                    | 005005002 QDII-REITs  |
| 006 FOF    | 006001 股票型FOF      | 006001001 股票型FOF      |
|            | 006002 混合型FOF      | 006002001 偏股混合型FOF    |
|            |                    | 006002002 平衡混合型FOF    |
|            |                    | 006002003 偏债混合型FOF    |
|            | 006003 债券型FOF      | 006003001 债券型FOF      |
|            | 006006 养老目标FOF     | 006006001 养老目标日期FOF   |
|            |                    | 006006002 养老目标风险FOF   |
| 007 另类投资基金 | 007001 基础设施REITs   | 007001001 基础设施REITs   |
|            | 007002 商品型基金       | 007002001 商品型基金       |
|            | 007003 量化对冲基金      | 007003001 量化对冲基金      |

## 使用示例

```sql
-- 查询当前可申购的普通股票型基金
SELECT c_fd_code, c_short_name, c_company_name, c_estabdate
FROM tytdata.tb_fd_basic_info
WHERE c_class1_code = '001'
  AND c_terminate_date IS NULL
  AND c_purchase_status = '开放申购';

-- 获取所有非定开且非持有期且成立日期早于2023-12-31的一级债基
SELECT *
FROM tytdata.tb_fd_basic_info
WHERE c_estabdate < '2023-12-31'
and c_terminate_date IS NULL
and c_class3_code = '003002001'  -- 一级债基
and c_regular_open_status = '0'  -- 非定开
and c_min_hold_period is Null;  -- 非持有期基金
```
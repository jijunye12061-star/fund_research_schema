# Python 编码规范

> 适用于 fund_research_schema 项目，研究环境优先简洁清晰。

## 核心原则

这是**研究环境**，不是生产系统。优先代码简洁可读，避免过度设计。

## 代码风格

### 极致简洁

- 单函数 ≤ 30 行，超过则拆分为私有函数（`_function_name`）
- 不添加冗余参数/选项，功能明确单一
- 不写防御性代码（try-except / 输入校验），研究环境可直接报错
- 避免嵌套 > 3 层，用 early return
- 用 `assert` 做必要的输入校验，不用 verbose 错误处理

### 类型提示

类型提示必须有，但不写冗长说明：

```python
def get_trade_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """获取交易日历，返回DatetimeIndex格式"""
    ...
```

### 注释规范

- 1 行 docstring 为主，说明函数用途即可
- 中文注释可接受，项目中广泛使用
- 不写冗长的 Args/Returns 说明（类型提示已经够了）

```python
# ✅ 好的
def calc_annualized_return(nav_series: pd.Series, days: int) -> float:
    """计算年化收益率（基于自然日365天）"""
    ...

# ❌ 过度注释
def calc_annualized_return(nav_series: pd.Series, days: int) -> float:
    """
    计算年化收益率
    
    Args:
        nav_series: 净值序列
        days: 天数
    Returns:
        float: 年化收益率
    Raises:
        ValueError: 如果天数为0
    """
    ...
```

### 命名规范

- 变量自解释：`fund_nav_df` 而非 `df1`
- 函数名动词开头：`get_`、`calc_`、`process_`、`_private_helper`
- 常量大写：`BATCH_SIZE = 100`、`ENV = 'dev'`
- 返回类型固定，不用 Optional 除非确实需要

### 数据处理

- 优先 pandas 向量化操作，避免 for 循环
- `pd.Timestamp` 作为标准 datetime 类型（桥接 `datetime.datetime` 和 `np.datetime64`）
- SQL 必须使用绑定变量（`:param`），**禁止 f-string 拼接**防止注入

```python
# ✅ 绑定变量
sql = "SELECT * FROM tb WHERE c_fd_code = :code"
df = oracle.query(sql, code='000001')

# ❌ f-string 拼接
sql = f"SELECT * FROM tb WHERE c_fd_code = '{code}'"
```

## 入口函数模式

每个 insert.py 统一使用 `run(date)` 作为入口，支持命令行参数：

```python
ENV = 'dev'  # 切换环境: 'dev' | 'prod'

def run(calc_date: str) -> None:
    """主入口，calc_date格式: YYYY-MM-DD"""
    df = _get_source_data(calc_date)
    with DorisConnector(ENV) as doris:
        doris.insert('tb_xxx', df)

if __name__ == '__main__':
    import sys
    biz_date = sys.argv[1] if len(sys.argv) > 1 else '2026-01-06'
    # DS传入格式为 %Y%m%d，需要转换
    biz_date = parse_biz_date(biz_date)
    run(biz_date)
```

## DolphinScheduler 路径适配

每个 insert.py 顶部需要路径适配代码，兼容本地开发和 DS 执行环境：

```python
import sys
from pathlib import Path

def _setup_path():
    """兼容本地和DS环境的路径适配"""
    for parent in Path(__file__).resolve().parents:
        if (parent / 'utils' / 'db_connector.py').exists():
            sys.path.insert(0, str(parent))
            return
    ds_resource = Path("dolphinscheduler/default/resources/jjy")
    if (ds_resource / 'utils' / 'db_connector.py').exists():
        sys.path.insert(0, str(ds_resource))
        return
    raise RuntimeError("找不到 utils 目录，请检查路径配置")

_setup_path()
```

> 不能提取到 `common.py`——鸡生蛋问题（要先设好路径才能 import common）。每个文件保留这段代码即可。

## 计算指标惯例

- **年化收益率**：基于自然日（365 天）
- **年化波动率**：基于交易日（252 天）
- **回撤和风险指标**：存储为正值（行业标准）
- **百分比**：存储为已乘 100 的值（如 5.2 表示 5.2%）
- **YTD/区间收益基准**：取上一期最后一个交易日（不是当期第一天），使用 `nav_adj_pre` 字段
- **两级指标体系**：基础指标（收益率、回撤）最低数据要求；风险调整指标（Sharpe、波动率）要求 ≥ 10 个交易日

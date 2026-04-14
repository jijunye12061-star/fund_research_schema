# Python 编码规范

> 适用于 fund_research_schema 项目，研究环境优先简洁清晰。

## 核心原则

这是**研究环境**，不是生产系统。优先代码简洁可读，避免过度设计。

---

## 代码风格

### 简洁

- 单函数 ≤ 30 行，超过则拆分为私有函数（`_function_name`）
- 不写防御性代码（try-except / 输入校验），研究环境直接报错即可
- 避免嵌套 > 3 层，用 early return

### 类型提示

必须有，docstring 一行说明用途即可，不写 Args/Returns/Raises 块。

```python
def get_trade_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """获取交易日历，返回DatetimeIndex格式"""
    ...
```

### 命名

- 变量自解释：`fund_nav_df` 而非 `df1`
- 函数名动词开头：`get_`、`calc_`、`process_`、`_private_helper`
- 常量大写：`BATCH_SIZE = 100`、`ENV = 'dev'`
- 中文注释可接受，项目中广泛使用

### 数据处理

- 优先 pandas 向量化操作，避免 for 循环
- SQL 必须使用绑定变量（`:param`），**禁止 f-string 拼接**

```python
# ✅ 绑定变量
sql = "SELECT * FROM tb WHERE c_fd_code = :code"
df = oracle.query(sql, code='000001')

# ❌ f-string 拼接
sql = f"SELECT * FROM tb WHERE c_fd_code = '{code}'"
```

---

## 入口函数模式

每个 insert.py 统一使用 `run(date)` 作为入口，`ENV` 声明在顶部。参数名随表类型而定：

- 日频表：`run(calc_date: str)` — 传交易日
- 季度/半年度表：`run(report_date: str)` — 传报告期末日期

```python
ENV = 'dev'  # 切换环境: 'dev' | 'prod'


def run(report_date: str) -> None:
    """主入口，report_date 格式: YYYY-MM-DD"""
    df = _get_source_data(report_date)
    with DorisConnector(ENV) as doris:
        doris.insert('tb_xxx', df)
```

`__main__` 的 DS 调度入口与补数循环模板见 [调度指南](scheduling-guide.md)。

---

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

> 不能提取到 `common.py`——要先设好路径才能 import common。每个文件保留这段代码。

---

## 计算指标惯例

- **年化收益率**：基于自然日（365 天）
- **年化波动率**：基于交易日（252 天）
- **YTD/区间收益基准**：取上一期最后一个交易日（不是当期第一天），使用 `nav_adj_pre` 字段
- **两级指标体系**：基础指标（收益率、回撤）最低数据要求；风险调整指标（Sharpe、波动率）要求 ≥ 10 个交易日
- **存储约定**（回撤正值、百分比乘 100 等）：见 [database-conventions.md](database-conventions.md)

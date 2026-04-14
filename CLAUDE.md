# CLAUDE.md

## 记忆文件（自动加载）

@.claude/memory/user_profile.md
@.claude/memory/business_rules_fund_data.md

## 场景识别（必读）

根据请求性质触发对应 skill，两个场景的规范完全独立，不要混用。

| 关键词 | Skill |
|--------|-------|
| 建表 / 加字段 / 改 schema / 改 DDL / 建视图 / insert.py / 调度 / 补数 / DBA | `infra` |
| 查 / 取数 / 筛选 / 导出 / 打分 / 统计 / 看数据 / 基金池 | `query` |

## 项目简介

Oracle (TYTFUND) → Apache Doris (tytdata) ETL 数据仓库，覆盖基金/A股/港股/债券/指数。
表定义在 `tables/tb_xxx/`，规范在 `docs/infra/`（基建）和 `docs/query/`（取数）。

## 安全规则（任何场景都适用）

- SQL **禁止 f-string 拼接**，只用绑定变量：`:param`（Oracle）/ `%s`（Doris）
- 禁止用 `to_sql` 写入 Doris，用 `doris.insert()`
- 禁止把 `database.yaml` / token 写入代码或提交 git

## Git 工作流

两个 remote：`master`（GitLab 内网，主协作）、`origin`（GitHub，个人备份）。

```bash
git pull master main && git push master main
git push origin main
```

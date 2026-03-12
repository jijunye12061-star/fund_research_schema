# Git 工作流

## 仓库配置

| Remote | 地址        | 用途               |
|--------|-----------|------------------|
| master | GitLab 内网 | 团队协作（与 laogu 协同） |
| origin | GitHub    | 个人备份             |

## 日常操作流程

```bash
# 1. 拉取 GitLab 最新代码
git pull master main

# 2. 本地开发、提交

# 3. 推送到 GitLab
git push master main

# 4. 同步到 GitHub 备份
git push origin main
```

## 分支策略

- Protected branch（main）使用 **merge**，不用 rebase（rebase 会产生重复提交）
- 遇到 `rejected (fetch first)` 错误时，先 `git pull master main` 再推
- 合并后历史会有分叉汇合线，这是正常的

## .gitignore 要点

```gitignore
# 敏感配置
config/database.yaml

# IDE
.idea/

# Python
__pycache__/
*.pyc
.env

# 日志
*.log
```

## 注意事项

- `database.yaml` 只提交 `.example` 模板
- GitLab Auto DevOps 已自动禁用，不需要 `.gitlab-ci.yml`
- 历史中曾暴露凭据，建议轮换相关密码

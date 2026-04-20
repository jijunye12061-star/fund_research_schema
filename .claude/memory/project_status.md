---
name: project_status
description: 数据平台建设进度——表上线状态、DBA 待办、调度配置情况
type: project
---

## 整体进度（截至 2026-04-20）

**已全部配齐 DS 调度**：日频层、中间层、标签层所有 insert.py 表均已配 DS 定时任务。

---

## DBA 待提视图（4 张，准备一次性提单）

| 表名 | 中文名 | 现状 | 备注 |
|------|--------|------|------|
| tb_stk_basic_info | A股基本信息 | temp_insert 临时方案 | 改为 Oracle→Doris 视图 |
| tb_stk_basic_info_hk | 港股基本信息 | temp_insert 临时方案 | 改为 Oracle→Doris 视图 |
| tb_fd_holder_structure | 基金持有人结构 | DBA 配置中 | 跟进视图上线 |
| tb_fd_holder_top10 | 基金前十大持有人 | DBA 配置中 | 跟进视图上线 |

**Why:** tb_stk_basic_info / _hk 目前用 temp_insert 绕过，需 DBA 正式建视图后切换；holder 两张表 DBA 早期已受理但未完成。
**How to apply:** 提 DBA 单时一次提 4 张，视图上线后将 catalog DS/状态 从 `视图待配` 改为 `视图`，并删除临时 insert 逻辑。

---

## 各层状态速查

| 层级 | 状态 |
|------|------|
| 数据源层——视图/按需表 | 视图类均已上线；4 张待 DBA |
| 日频计算层 | 全部 ✓（industry / concept / perform_abs / industry_hk） |
| 中间层 | 全部 ✓ |
| 标签层 | 全部 ✓ |

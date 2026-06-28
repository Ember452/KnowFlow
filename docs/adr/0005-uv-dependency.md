# ADR 0005: 依赖管理用 uv

- 状态: Accepted
- 日期: 2026-06-04
- 关联: 设计文档 D4 / P0 脚手架

## Context

Python 依赖管理主流方案：pip + requirements.txt / poetry / uv。
项目需要：锁文件保证可复现、dev/运行时依赖分离、安装速度快、与 CI/容器构建集成简单。
2024-2025 年 uv 已成 Python 生态主流工具（Astral 出品，Rust 实现），安装比 pip/poetry 快 10-100x。

## Decision

**采用 uv 管理依赖**：`pyproject.toml` 声明依赖（`[project]` + `[dependency-groups]`），`uv.lock` 锁定全量版本，`uv sync` 一键安装。
工程门禁（ruff/mypy/pytest）统一经 `uv run` 执行；Docker 构建在 builder 阶段用 `uv sync --frozen` 保证镜像可复现。

## Consequences

正面:
- 锁文件可复现: uv.lock 全量锁定, CI/本地/容器三方一致.
- 安装极快: 并发下载 + 全局缓存, 冷启动 <1min.
- 工具链统一: uv run 替代 pip/poetry/venv 组合, 心智负担低.

负面:
- uv 迭代快(版本升级偶有行为变化), 需锁版本(CI 固定 setup-uv 版本).
- 团队若习惯 pip 需一次学习成本.

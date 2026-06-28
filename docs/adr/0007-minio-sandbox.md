# ADR 0007: 沙盒用 MinIO 不用本地文件系统

- 状态: Accepted
- 日期: 2026-06-06
- 关联: 设计文档 D6 / P9 沙盒文件系统

## Context

工具（file_tools）与上下文卸载（spiller）需要文件读写能力，同时要保证多会话隔离与安全。
方案：宿主机本地文件系统（按会话建目录）或对象存储 MinIO（按 bucket prefix 隔离）。

本地文件系统的风险：路径穿越（`../`）校验一旦遗漏即越权访问宿主文件、跨会话目录隔离靠约定、
容器环境无状态（Pod 重建文件丢失）。
MinIO 天然以对象隔离（`sessions/{sid}/workspace/` prefix），对象键不含真实路径层级，
无宿主文件系统越权面，且原生支持配额与 TTL 生命周期管理。

## Decision

**沙盒文件系统用 MinIO 做后端**：`sandbox/virtual_path.py` 维护 `/workspace/x.json ↔ MinIO key` 映射，
`access_control.py` 在虚拟路径层拦截 `../`、绝对路径与跨会话访问，`quota.py` 按会话限配额（默认 100MB），
`lifecycle.py` 按会话 TTL 清理。file_tools 与上下文卸载统一走沙盒接口，不直接接触文件系统。

## Consequences

正面:
- 安全面收敛: 对象存储无目录穿越语义, 越权面从"路径校验"收窄为"key 前缀校验".
- 天然隔离: bucket prefix 即会话边界, 跨会话访问被存储层拒绝.
- 生命周期管理: 配额/TTL 由对象存储特性支撑, 不依赖宿主机脚本.

负面:
- 引入 MinIO 依赖(与 Milvus 内部 MinIO 分开部署, 见 docker-compose).
- 沙盒内文件非 POSIX 语义(无 inode/硬链接), 对文件型工具(Skill 读写)无影响.
- 大文件读写多一次网络往返, 沙盒内文件大小受限(配额内).

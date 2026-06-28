# ADR 0001: 图存储用 PostgreSQL 而非 Neo4j

- 状态: Accepted
- 日期: 2026-06-02
- 关联: 设计文档 D1 / 3.4 模块二

## Context

GraphRAG 检索需要实体关系图谱支持一跳扩展（由命中 chunk 的实体找到共享实体的关联 chunk）。
选型时有两条路：专用图数据库（Neo4j）或复用现有 PostgreSQL 关系表（entities / relations）。

Neo4j 的优势在多跳遍历与图算法，但引入独立组件意味着：额外部署、数据一致性同步、运维成本。
本场景的检索扩展深度只有一跳，SQL JOIN 即可完成。

## Decision

**实体与关系存 PostgreSQL**（`entities` / `relations` 两张表），一跳扩展用一条 SQL JOIN 实现；
架构保留升级路径——后续需要多跳或图规模爆发时再引入 Neo4j，图谱查询封装在 `graph_store.py` 单一出口。

## Consequences

正面:
- 无额外组件: 图谱与业务数据同库, 事务一致, 部署简化.
- 一跳扩展毫秒级: 单条 JOIN 完成跨文档关联, 延迟可控.
- 面试叙事清晰: "不过度设计, 用 SQL 解决一跳扩展".

负面:
- 多跳深度遍历性能差(递归 CTE 可部分缓解), 当前场景用不到.
- 图谱分析类能力(社区发现/中心度)不可用, 后续需要时再迁移.

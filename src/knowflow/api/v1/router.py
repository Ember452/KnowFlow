"""v1 路由聚合 - 挂载全部 v1 端点模块."""

from fastapi import APIRouter

from knowflow.api.v1.endpoints import (
    agent,
    chat,
    document,
    eval,
    health,
    knowledge,
    memory,
    report,
    skill,
    tools,
    trace,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(document.router)
router.include_router(knowledge.router)
router.include_router(chat.router)
router.include_router(agent.router)
router.include_router(skill.router)
router.include_router(tools.router)
router.include_router(memory.router)
router.include_router(trace.router)
router.include_router(eval.router)
router.include_router(report.router)

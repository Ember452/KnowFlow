# Multi-Agent 断点续跑演示脚本

> M7(P8) 验收演示: 复杂任务委派执行中 kill 进程 → 从 checkpoint 恢复继续执行。
> 前置: docker compose 四件套就绪 + `.env` 配置 LLM API Key(委派链路需真实 LLM 规划/汇总)。

## 演示原理

- 每个 Agent run 对应一条 LangGraph 线程(`thread_id = str(agent_run_id)`), 状态机
  每个节点边界自动写入 checkpoint(checkpoints / checkpoint_blobs / checkpoint_writes 表),
  原生维护 `parent_checkpoint_id` 形成父子链(决策见 docs/adr/0004)。
- 断点续跑 = 以同一 `thread_id` + 记录的 `checkpoint_id` 调 `graph.ainvoke`,
  LangGraph 从该 checkpoint 恢复 channel 状态继续执行。
- 委派里程碑: `task_delegations.checkpoint_id` 记录 execute 节点后的 checkpoint,
  可精确定位"委派已创建但子任务未完成"的恢复点。

## 演示步骤(PowerShell)

```powershell
# 1. 启动服务(另开终端)
uv run uvicorn knowflow.main:app --port 8000

# 2. 触发复杂任务委派(对比类问题 → understand=complex → LLM 规划 → 委派)
$resp = curl.exe -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"对比 A/B/C 三款产品的价格与参数并汇总"}'
$resp

# 3. 从响应 progress 事件/数据库查主 run_id(agent_runs 表 agent_type=main)
# 查看父子 run 记录与委派链(验收标准: 状态机可见)
curl.exe -s http://localhost:8000/api/v1/agents/runs/1

# 4. 断点续跑演示(checkpoint 恢复):
#    步骤 2 运行中(Ctrl+C)或完成后, 用 python 直接恢复状态:
uv run python -c "
import asyncio
from knowflow.agents.checkpoint import CheckpointManager

async def main():
    mgr = CheckpointManager()
    # run_id=1 的最新 checkpoint(委派完成后)
    state = await mgr.restore('1')
    print('恢复状态:', state.get('query'))
    print('needs_delegation:', state.get('needs_delegation'))
    print('子任务结果:', state.get('subtask_results'))
    chain = await mgr.lineage('1')
    print('checkpoint 父子链深度:', len(chain))

asyncio.run(main())
"
```

## 预期输出

1. 步骤 2 返回答案含三个产品的对比汇总(子 Agent 并发执行后主 Agent 汇总)
2. 步骤 3 返回 `run.agent_type="main"` + 2-3 个 `children`(sub) + 对应 `delegations`(completed)
3. 步骤 4 恢复出的状态含 `query`、`needs_delegation=true`、`subtask_results` 各子任务输出;
   `lineage` 返回链长度 >= 3(understand/plan/execute 里程碑), 每项含 `parent_checkpoint_id`

## 原理说明(面试口径)

- **为什么用 LangGraph 原生 checkpoint 而非自研**: 序列化协议(channel versions /
  checkpoint_blobs / checkpoint_writes)、时间旅行、parent 链原生支持, 只做
  CheckpointManager 门面(save/restore/lineage), 见 ADR 0004。
- **thread_id = agent_run_id**: 一个 run 一条线程, 线程内连续 checkpoint 天然成链,
  kill 后以 thread_id + checkpoint_id 恢复。
- **父子 run 与委派链**: agent_runs.parent_run_id 记录 main→sub, task_delegations
  记录任务级状态机(created→delegated→running→completed/failed), 与 checkpoint 解耦:
  checkpoint 管"状态恢复", 委派表管"业务可见性"。

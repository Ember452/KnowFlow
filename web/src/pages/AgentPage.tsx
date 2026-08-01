/**
 * Agent 编排可视化(核心页): 四面板联动.
 * ① 状态机流程图(ReactFlow) ② 子任务委派链 ③ 事件时间线 ④ Trace 树 + 原始事件查看器.
 * 事件驱动: progress → execute/summarize; token → summarize; done → 拉取委派链与 Trace 补全.
 */

import { useCallback, useState } from "react";
import { getAgentRun, getTraceTree } from "../api/endpoints";
import AgentFlowChart, { type FlowNodeState } from "../components/agent/AgentFlowChart";
import { Button, Card, EmptyState, ErrorAlert, PageHeader, StatusBadge } from "../components/common";
import { TraceTreeView } from "../components/TraceTree";
import { useChatStream } from "../hooks/useChatStream";
import { useSession } from "../stores/SessionContext";
import type {
  AgentRunDetail,
  TaskDelegationInfo,
  ToolEndEvent,
  ToolStartEvent,
  TraceSpanNode,
} from "../types/api";

const EXAMPLE_QUERIES = [
  "对比产品 A/B/C 的价格与参数并汇总",
  "基于知识库总结报销与差旅制度",
  "帮我查询今天天气并计算两个城市温差",
];

function SubtaskPanel({
  runDetail,
  toolStarts,
  toolEnds,
  subtaskIds,
}: {
  runDetail: AgentRunDetail | null;
  toolStarts: ToolStartEvent[];
  toolEnds: ToolEndEvent[];
  subtaskIds: (string | number)[];
}) {
  const delegations = runDetail?.delegations ?? [];
  const entries: { id: string | number; info?: TaskDelegationInfo }[] = subtaskIds.map((id) => ({
    id,
    info: delegations.find((d) => String(d.id) === String(id)),
  }));

  if (entries.length === 0 && !runDetail) {
    return <EmptyState text="暂无子任务" hint="发送复杂任务触发委派后此处展示委派链" />;
  }

  const toolCountFor = (id: string | number) =>
    toolStarts.filter((t) => String(t.subtask_id) === String(id)).length;

  return (
    <div className="space-y-2">
      {entries.map(({ id, info }) => {
        const failed = toolEnds.find((t) => String(t.subtask_id) === String(id) && !t.success);
        const status = info?.status ?? (failed ? "failed" : toolCountFor(id) > 0 ? "running" : "created");
        return (
          <div
            key={String(id)}
            className={`rounded-lg border p-2.5 ${failed ? "border-red-200 bg-red-50" : "border-gray-200 bg-gray-50"}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-xs font-medium text-gray-700">
                {info?.task ?? `子任务 #${id}`}
              </span>
              <StatusBadge status={status} />
            </div>
            <div className="mt-1 flex items-center gap-3 text-[10px] text-gray-400">
              <span>ID: {String(id)}</span>
              {info?.created_at && (
                <span>{new Date(info.created_at).toLocaleTimeString()}</span>
              )}
              {info?.checkpoint_id && (
                <span className="truncate" title={info.checkpoint_id}>
                  ckpt: {info.checkpoint_id.slice(0, 16)}…
                </span>
              )}
              <span>{toolCountFor(id)} 次工具调用</span>
            </div>
            {failed && (
              <div className="mt-1 truncate text-[10px] text-red-500 dark:text-red-400" title={failed.error ?? ""}>
                {failed.error ?? "工具调用失败"}
              </div>
            )}
          </div>
        );
      })}
      {runDetail && runDetail.children.length > 0 && (
        <div className="pt-1 text-[10px] text-gray-400">
          共 {runDetail.children.length} 个子 Agent run · 主 run #{runDetail.run.id} ({runDetail.run.status})
        </div>
      )}
    </div>
  );
}

interface TimelineItem {
  ts: number;
  type: "retrieval" | "tool_start" | "tool_end" | "token" | "done" | "progress" | "error";
  label: string;
  detail?: string;
  ok?: boolean;
}

function EventTimeline({ items }: { items: TimelineItem[] }) {
  if (items.length === 0) return <EmptyState text="暂无事件" hint="发送后此处实时展示 SSE 事件时间线" />;
  return (
    <div className="relative space-y-2 pl-4">
      <div className="absolute bottom-1 left-[5px] top-1 w-px bg-gray-200" />
      {items.map((item, i) => (
        <div key={i} className="relative flex items-start gap-2">
          <span
            className={`absolute -left-4 top-1 h-2.5 w-2.5 rounded-full border-2 border-white dark:border-gray-800 ${
              item.type === "error" ? "bg-red-500" : item.ok === false ? "bg-red-500" : item.type === "tool_end" ? "bg-blue-500" : item.type === "token" ? "bg-amber-400" : "bg-green-500"
            }`}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-gray-700">{item.label}</span>
              {item.ok !== undefined && <span className={item.ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>{item.ok ? "✓" : "✗"}</span>}
              <span className="text-[10px] text-gray-400">{new Date(item.ts).toLocaleTimeString()}</span>
            </div>
            {item.detail && <div className="mt-0.5 truncate font-mono text-[10px] text-gray-500" title={item.detail}>{item.detail}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AgentPage() {
  const { userId } = useSession();
  const [input, setInput] = useState("");
  const [flowStates, setFlowStates] = useState<Record<string, FlowNodeState>>({});
  const [runDetail, setRunDetail] = useState<AgentRunDetail | null>(null);
  const [traceRoots, setTraceRoots] = useState<TraceSpanNode[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [devMode, setDevMode] = useState(false);
  const [delegated, setDelegated] = useState(false);

  const { state, send } = useChatStream({
    onRaw: () => {
      /* 原始事件由 state.rawEvents 统一渲染 */
    },
    onProgress: (e) => {
      setDelegated(!!e.delegated);
      setTimeline((t) => [...t, { ts: Date.now(), type: "progress", label: "编排进度", detail: `delegated=${e.delegated} subtasks=${(e.subtasks ?? []).length}` }]);
      setFlowStates((s) => ({ ...s, understand: "completed", plan: "completed", execute: e.delegated ? "running" : "skipped", summarize: "running" }));
    },
    onRetrieval: (e) => {
      setTimeline((t) => [...t, { ts: Date.now(), type: "retrieval", label: "混合检索", detail: `${e.chunks.length} chunks · ${e.latency_ms.toFixed(1)} ms` }]);
    },
    onToolStart: (e) => {
      setTimeline((t) => [...t, { ts: Date.now(), type: "tool_start", label: `工具调用 ${e.tool}` }]);
    },
    onToolEnd: (e) => {
      setTimeline((t) => [...t, { ts: Date.now(), type: "tool_end", label: `工具完成 ${e.tool}`, detail: `${e.latency_ms.toFixed(1)} ms`, ok: e.success }]);
    },
    onToken: () => {
      setFlowStates((s) => ({ ...s, summarize: "running" }));
    },
    onDone: (e) => {
      setFlowStates((s) => ({ ...s, summarize: "completed", end: "completed" }));
      setTimeline((t) => [...t, { ts: Date.now(), type: "done", label: "完成", detail: `${e.tokens} tokens · ${e.latency_ms.toFixed(1)} ms` }]);
      // 补全委派链与 Trace 树
      void (async () => {
        const progress = state.progress;
        if (progress?.run_id) {
          try {
            const detail = await getAgentRun(Number(progress.run_id));
            setRunDetail(detail);
            setFlowStates((s) => ({ ...s, execute: "completed" }));
          } catch {
            // 委派链查询失败不阻塞页面
          }
        }
        try {
          const tree = await getTraceTree(e.session_id);
          setTraceRoots(tree.roots);
        } catch {
          // 无 Trace 记录时保持空态
        }
      })();
    },
    onError: (msg) => {
      setTimeline((t) => [...t, { ts: Date.now(), type: "error", label: "错误", detail: msg }]);
      setFlowStates((s) => ({ ...s, summarize: "failed" }));
    },
  });

  const submit = (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || state.running) return;
    setInput("");
    setRunDetail(null);
    setTraceRoots([]);
    setTimeline([]);
    setDelegated(false);
    setFlowStates({ understand: "running" });
    void send(message, null, userId);
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader
        title="Agent 编排"
        desc="实时观察状态机流转、子任务委派与工具调用轨迹"
        actions={
          <Button
            variant={devMode ? "primary" : "outline"}
            size="sm"
            onClick={() => setDevMode((v) => !v)}
          >
            {devMode ? "原始事件已开启" : "原始事件"}
          </Button>
        }
      />

      {/* 输入区 */}
      <Card>
        <div className="mb-2 flex flex-wrap gap-1.5">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => submit(q)}
              disabled={state.running}
              className="rounded-full border border-gray-200 bg-surface px-2.5 py-1 text-xs text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 disabled:opacity-50 dark:hover:border-blue-500 dark:hover:text-blue-400"
            >
              {q}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && submit()}
            disabled={state.running}
            placeholder="输入复杂任务，观察多 Agent 委派（如：对比产品 A/B/C 并汇总）"
            className="h-10 flex-1 rounded-lg border border-gray-300 px-3 text-sm outline-none focus:border-blue-500"
          />
          <Button onClick={() => submit()} disabled={state.running || !input.trim()}>
            {state.running ? "编排中…" : "发送"}
          </Button>
        </div>
      </Card>

      {state.error && <ErrorAlert message={state.error} />}

      {/* 四面板 */}
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
        <Card title="状态机流程图" className="h-full">
          <AgentFlowChart states={flowStates} subtaskCount={state.progress?.subtasks?.length ?? runDetail?.delegations.length} delegated={delegated} />
        </Card>
        <Card title="子任务委派链" className="h-full">
          <SubtaskPanel runDetail={runDetail} toolStarts={state.toolStarts} toolEnds={state.toolEnds} subtaskIds={state.progress?.subtasks ?? []} />
        </Card>
        <Card title="事件时间线" className="h-full">
          <EventTimeline items={timeline} />
        </Card>
        <Card title="Trace 树" className="h-full">
          <div className="max-h-full overflow-auto">
            <TraceTreeView roots={traceRoots} maxHeight={200} />
          </div>
        </Card>
      </div>

      {/* 原始事件查看器 */}
      {devMode && (
        <Card title={`原始 SSE 事件 (${state.rawEvents.length})`}>
          {state.rawEvents.length === 0 ? (
            <EmptyState text="暂无事件" />
          ) : (
            <div className="max-h-64 space-y-1 overflow-auto font-mono text-xs">
              {state.rawEvents.map((ev, i) => (
                <div key={i} className="rounded bg-gray-50 px-2 py-1">
                  <span className="mr-2 font-semibold text-blue-600">{ev.event}</span>
                  <span className="text-gray-600">{JSON.stringify(ev.data)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

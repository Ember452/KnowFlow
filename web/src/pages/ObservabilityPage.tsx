/**
 * 可观测: 会话统计卡 + 选会话 Trace 树 + Replay 时间轴回放.
 */

import { useCallback, useEffect, useState } from "react";
import { getTraceStats, getTraceTree, replayTrace } from "../api/endpoints";
import { Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner, StatCard } from "../components/common";
import { TraceTreeView } from "../components/TraceTree";
import { useSession } from "../stores/SessionContext";
import type { ReplayEvent, TraceSpanNode, TraceStats } from "../types/api";

function ReplayTimeline({ events }: { events: ReplayEvent[] }) {
  if (events.length === 0) return <EmptyState text="无回放事件" />;
  return (
    <div className="space-y-1.5">
      {events.map((ev, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5">
          <span className="shrink-0 font-mono text-[10px] text-gray-400">{new Date(ev.ts).toLocaleTimeString()}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-medium text-gray-700">{ev.name}</span>
              <span className="rounded bg-surface/70 px-1 py-0.5 text-[10px] text-gray-500">{ev.span_type}</span>
            </div>
            {ev.output && <div className="mt-0.5 truncate text-[10px] text-gray-500">{JSON.stringify(ev.output).slice(0, 200)}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

function spanSummary(counts: TraceStats["span_counts"]): string {
  return Object.entries(counts)
    .map(([k, v]) => `${k} ${v}`)
    .join(" · ");
}

export default function ObservabilityPage() {
  const { sessions } = useSession();
  const [stats, setStats] = useState<TraceStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [traceRoots, setTraceRoots] = useState<TraceSpanNode[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [checkpointId, setCheckpointId] = useState("");
  const [replay, setReplay] = useState<ReplayEvent[] | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    try {
      const s = await getTraceStats(24);
      setStats(s);
      setStatsError(null);
    } catch (e) {
      setStatsError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  const loadTrace = async (sid: number) => {
    setSessionId(sid);
    setTraceLoading(true);
    setTraceError(null);
    setTraceRoots([]);
    setReplay(null);
    try {
      const tree = await getTraceTree(sid);
      setTraceRoots(tree.roots);
    } catch (e) {
      setTraceError(e instanceof Error ? e.message : String(e));
    } finally {
      setTraceLoading(false);
    }
  };

  const doReplay = async () => {
    if (sessionId == null) return;
    setReplayLoading(true);
    setReplayError(null);
    try {
      const resp = await replayTrace(sessionId, checkpointId.trim() || null);
      setReplay(resp.events);
    } catch (e) {
      setReplayError(e instanceof Error ? e.message : String(e));
    } finally {
      setReplayLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader title="可观测" desc="会话 Trace 树与事件回放" />

      {/* 统计卡 */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard label="近 24h 对话数" value={stats?.dialogs ?? "-"} />
        <StatCard label="Trace 数" value={stats?.traces ?? "-"} />
        <StatCard label="工具调用" value={stats?.tool_calls ?? "-"} sub="含子 Agent" />
        <StatCard
          label="工具成功率"
          value={stats ? `${(stats.tool_success_rate * 100).toFixed(1)}%` : "-"}
          accent="text-green-600"
        />
        <StatCard
          label="Span 类型分布"
          value={Object.keys(stats?.span_counts ?? {}).length || "-"}
          sub={stats ? spanSummary(stats.span_counts) : undefined}
        />
      </div>
      {statsError && <ErrorAlert message={statsError} onRetry={() => void loadStats()} />}

      <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
        {/* Trace 树 */}
        <Card
          title="会话 Trace 树"
          className="h-full"
          actions={
            <select
              value={sessionId ?? ""}
              onChange={(e) => e.target.value && void loadTrace(Number(e.target.value))}
              className="h-8 rounded-lg border border-gray-300 px-2 text-xs outline-none focus:border-blue-500"
            >
              <option value="">选择会话</option>
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  会话 #{s.id}
                </option>
              ))}
            </select>
          }
        >
          {traceLoading ? (
            <Spinner text="加载 Trace…" />
          ) : traceError ? (
            <ErrorAlert message={traceError} />
          ) : (
            <div className="max-h-full overflow-auto">
              <TraceTreeView roots={traceRoots} maxHeight={160} />
            </div>
          )}
        </Card>

        {/* Replay */}
        <Card
          title="会话 Replay 回放"
          className="h-full"
          actions={
            <Button
              variant="primary"
              size="sm"
              onClick={() => void doReplay()}
              disabled={replayLoading || sessionId == null}
            >
              {replayLoading ? "回放中…" : "回放"}
            </Button>
          }
        >
          <div className="mb-2 flex items-center gap-2">
            <input
              value={checkpointId}
              onChange={(e) => setCheckpointId(e.target.value)}
              placeholder="checkpoint_id(可选)"
              className="h-8 flex-1 rounded-lg border border-gray-300 px-2 font-mono text-xs outline-none focus:border-blue-500"
            />
          </div>
          {replayError && <div className="mb-2"><ErrorAlert message={replayError} /></div>}
          <div className="max-h-full overflow-auto">
            {replay ? <ReplayTimeline events={replay} /> : <EmptyState text="选择会话后回放时间序事件" />}
          </div>
        </Card>
      </div>
    </div>
  );
}

/**
 * Trace 树查看器: Agent 编排页与可观测页共用.
 */

import { useState } from "react";
import { EmptyState, JsonViewer } from "./common";
import type { TraceSpanNode } from "../types/api";

const SPAN_COLORS: Record<string, string> = {
  agent_decision: "border-purple-200 bg-purple-50",
  tool_call: "border-blue-200 bg-blue-50",
  retrieval: "border-green-200 bg-green-50",
  memory_recall: "border-orange-200 bg-orange-50",
};

export function TraceTreeView({
  roots,
  depth = 0,
  maxHeight = 200,
}: {
  roots: TraceSpanNode[];
  depth?: number;
  maxHeight?: number;
}) {
  const [open, setOpen] = useState<Record<number, boolean>>({});
  if (roots.length === 0) return <EmptyState text="无 Trace 记录" />;
  return (
    <div className="space-y-1.5">
      {roots.map((node) => (
        <div key={node.id}>
          <div
            className={`rounded-lg border p-2 ${SPAN_COLORS[node.span_type] ?? "border-gray-200 bg-gray-50"}`}
            style={{ marginLeft: depth * 16 }}
          >
            <button
              onClick={() => setOpen((o) => ({ ...o, [node.id]: !o[node.id] }))}
              className="flex w-full items-center justify-between gap-2 text-left"
            >
              <span className="flex min-w-0 items-center gap-2">
                {node.children.length > 0 && (
                  <span className="text-xs text-gray-400">{open[node.id] ? "▾" : "▸"}</span>
                )}
                <span className="truncate font-mono text-xs font-medium text-gray-700">{node.name}</span>
                <span className="rounded bg-surface/70 px-1 py-0.5 text-[10px] text-gray-500">{node.span_type}</span>
              </span>
              <span className="shrink-0 text-[10px] text-gray-400">
                {node.latency_ms != null ? `${node.latency_ms.toFixed(1)} ms` : "-"}
              </span>
            </button>
            {open[node.id] && (
              <div className="mt-2">
                <JsonViewer data={{ input: node.input, output: node.output }} defaultCollapsed maxHeight={maxHeight} />
              </div>
            )}
          </div>
          {open[node.id] && <TraceTreeView roots={node.children} depth={depth + 1} maxHeight={maxHeight} />}
        </div>
      ))}
    </div>
  );
}

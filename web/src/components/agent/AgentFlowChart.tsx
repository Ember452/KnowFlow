/**
 * Agent 状态机流程图(ReactFlow): START→understand→plan→execute→summarize→END.
 * 节点状态由 SSE 事件驱动: idle 灰 / running 蓝(脉冲) / completed 绿 / failed 红.
 * execute 节点内嵌子任务徽标, summarize 收 token 流后置 completed.
 */

import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";

export type FlowNodeState = "idle" | "running" | "completed" | "failed" | "skipped";

interface FlowNodeData extends Record<string, unknown> {
  label: string;
  state?: FlowNodeState;
  subtasks?: number;
}

type FlowNodeType = Node<FlowNodeData>;

type NodeRecord = Record<string, FlowNodeState>;

const NODE_STYLE: Record<FlowNodeState, string> = {
  idle: "border-gray-300 bg-white text-gray-500 dark:bg-surface",
  running: "border-blue-500 bg-blue-50 text-blue-700 animate-pulse dark:text-blue-300",
  completed: "border-green-500 bg-green-50 text-green-700 dark:text-green-300",
  failed: "border-red-500 bg-red-50 text-red-700 dark:text-red-300",
  skipped: "border-gray-200 bg-gray-50 text-gray-400",
};

function FlowNode({ data }: NodeProps<FlowNodeType>) {
  const state: FlowNodeState = data.state ?? "idle";
  return (
    <div
      className={`relative rounded-xl border-2 px-4 py-2.5 text-sm font-semibold shadow-sm transition-colors ${NODE_STYLE[state]}`}
    >
      {data.subtasks ? (
        <div className="flex items-center gap-2">
          <span>{data.label}</span>
          <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-normal text-indigo-700">
            {data.subtasks} 子任务
          </span>
        </div>
      ) : (
        data.label
      )}
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

const nodeTypes = { flow: FlowNode };

interface AgentFlowChartProps {
  states: NodeRecord;
  subtaskCount?: number;
  delegated?: boolean;
}

export default function AgentFlowChart({ states, subtaskCount = 0, delegated = false }: AgentFlowChartProps) {
  const nodes: FlowNodeType[] = useMemo(
    () => [
      { id: "start", type: "flow", position: { x: 0, y: 130 }, data: { label: "START", state: "completed" } },
      { id: "understand", type: "flow", position: { x: 140, y: 130 }, data: { label: "understand", state: states.understand ?? "idle" } },
      { id: "plan", type: "flow", position: { x: 280, y: 130 }, data: { label: "plan", state: states.plan ?? "idle" } },
      {
        id: "execute",
        type: "flow",
        position: { x: 420, y: 130 },
        data: {
          label: "execute",
          state: delegated ? states.execute ?? "completed" : states.execute ?? "skipped",
          subtasks: subtaskCount || undefined,
        },
      },
      { id: "summarize", type: "flow", position: { x: 580, y: 130 }, data: { label: "summarize", state: states.summarize ?? "idle" } },
      { id: "end", type: "flow", position: { x: 740, y: 130 }, data: { label: "END", state: states.end ?? "idle" } },
    ],
    [states, subtaskCount, delegated]
  );

  const edges: Edge[] = useMemo(
    () =>
      ["start-understand", "understand-plan", "plan-execute", "execute-summarize", "summarize-end"].map((id, i) => ({
        id,
        source: id.split("-")[0],
        target: id.split("-")[1],
        type: "smoothstep",
        animated: false,
        style: { stroke: "#cbd5e1", strokeWidth: 1.5 },
      })),
    []
  );

  return (
    <div className="h-56 w-full">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }} minZoom={0.5}>
        <Background gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

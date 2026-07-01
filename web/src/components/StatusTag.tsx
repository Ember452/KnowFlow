import { Tag } from 'antd';
import type { DocumentStatus, RunStatus, EvalStatus, ExecutionDomain, SpanType } from '@/types';

const PALETTE = {
  ok: { color: '#4f5d3a', bg: '#e7ecdd', border: '#d3dcc1' },
  run: { color: '#934828', bg: '#f4e0d5', border: '#ebc6b6' },
  warn: { color: '#b0562f', bg: '#fbf2ed', border: '#f4e0d5' },
  err: { color: '#732222', bg: '#f7dedb', border: '#f3c4bf' },
  // mute 用语义变量：暗色模式下随主题切换
  mute: { color: 'var(--kf-text-2)', bg: 'var(--kf-surface-tint)', border: 'var(--kf-bubble-border)' },
} as const;

function tag(status: string, kind: keyof typeof PALETTE) {
  const p = PALETTE[kind];
  return (
    <Tag style={{ color: p.color, background: p.bg, borderColor: p.border, borderRadius: 6, margin: 0 }}>
      {status}
    </Tag>
  );
}

export function DocStatusTag({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, keyof typeof PALETTE> = {
    ready: 'ok',
    indexing: 'run',
    reindexing: 'warn',
    failed: 'err',
  };
  const label: Record<DocumentStatus, string> = {
    ready: '已就绪',
    indexing: '索引中',
    reindexing: '重建中',
    failed: '失败',
  };
  return tag(label[status], map[status]);
}

export function RunStatusTag({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, keyof typeof PALETTE> = {
    completed: 'ok',
    running: 'run',
    pending: 'mute',
    failed: 'err',
  };
  const label: Record<RunStatus, string> = {
    completed: '已完成',
    running: '运行中',
    pending: '等待中',
    failed: '失败',
  };
  return tag(label[status], map[status]);
}

export function EvalStatusTag({ status }: { status: EvalStatus }) {
  const map: Record<EvalStatus, keyof typeof PALETTE> = {
    completed: 'ok',
    running: 'run',
    queued: 'mute',
    failed: 'err',
  };
  const label: Record<EvalStatus, string> = {
    completed: '已完成',
    running: '运行中',
    queued: '排队中',
    failed: '失败',
  };
  return tag(label[status], map[status]);
}

export function DomainTag({ domain }: { domain: ExecutionDomain }) {
  const map: Record<ExecutionDomain, keyof typeof PALETTE> = {
    direct: 'ok',
    skill_only: 'run',
    subagent_only: 'warn',
    internal: 'mute',
  };
  const label: Record<ExecutionDomain, string> = {
    direct: 'direct · 始终可见',
    skill_only: 'skill_only · 激活注入',
    subagent_only: 'subagent · 仅子Agent',
    internal: 'internal · 系统内部',
  };
  return tag(label[domain], map[domain]);
}

export function SpanTypeTag({ type }: { type: SpanType }) {
  const label: Record<SpanType, string> = {
    root: 'root',
    agent_decision: '决策',
    tool_call: '工具',
    retrieval: '检索',
    memory_recall: '记忆',
  };
  const map: Record<SpanType, keyof typeof PALETTE> = {
    root: 'mute',
    agent_decision: 'run',
    tool_call: 'warn',
    retrieval: 'ok',
    memory_recall: 'mute',
  };
  return tag(label[type], map[type]);
}

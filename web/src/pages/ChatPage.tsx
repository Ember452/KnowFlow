/**
 * 对话工作台: 会话列表 + SSE 流式对话 + 引用块 + 工具调用记录.
 * 事件驱动: retrieval → 引用块; tool_start/tool_end → 工具记录; token → 打字机; done → 收尾.
 */

import { useCallback, useRef, useState } from "react";
import { listMessages } from "../api/endpoints";
import MarkdownBody from "../components/MarkdownBody";
import { Button, Card, EmptyState, ErrorAlert, IconButton, SkeletonLines } from "../components/common";
import { Icon } from "../components/icons";
import { useChatStream } from "../hooks/useChatStream";
import { useSession } from "../stores/SessionContext";
import type { Citation, MessageOut, ToolCallRecord } from "../types/api";

const EXAMPLE_QUERIES = [
  "对比产品 A/B/C 的价格与参数并汇总",
  "基于知识库总结报销与差旅制度",
  "帮我查询今天天气并计算两个城市温差",
];

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolCalls?: ToolCallRecord[];
  error?: string;
}

function CitationsBlock({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false);
  if (citations.length === 0) return null;
  return (
    <div className="mt-2 border-t border-gray-100 pt-1.5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs font-medium text-blue-600 hover:underline"
      >
        {open ? "收起" : "展开"}引用 ({citations.length})
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {citations.map((c, i) => (
            <div key={c.chunk_id} className="rounded-lg border border-blue-100 bg-blue-50/50 px-2.5 py-1.5 text-xs">
              <div className="mb-0.5 flex items-center gap-2">
                <span className="font-semibold text-blue-700 dark:text-blue-300">[{i + 1}]</span>
                <span className="text-gray-500">{c.doc_title ?? `文档 #${c.doc_id ?? "-"}`}</span>
                <span className="text-gray-400">score {c.score?.toFixed(3)}</span>
                <span className="text-gray-400">{c.source}</span>
              </div>
              <div className="line-clamp-2 text-gray-600">{c.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ToolCallList({ toolCalls }: { toolCalls: ToolCallRecord[] }) {
  if (toolCalls.length === 0) return null;
  return (
    <div className="mt-2 space-y-1">
      {toolCalls.map((tc, i) => (
        <div
          key={i}
          className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs"
        >
          <span className={tc.success ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>{tc.success ? "✓" : "✗"}</span>
          <span className="font-mono font-medium text-gray-700">{tc.tool}</span>
          <span className="text-gray-400">{tc.latency_ms.toFixed(1)} ms</span>
          {tc.error && <span className="truncate text-red-500 dark:text-red-400">{tc.error}</span>}
        </div>
      ))}
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-400"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </span>
  );
}

function AssistantAvatar() {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white">
      <Icon name="sparkles" className="h-3.5 w-3.5" />
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-200 text-[11px] font-semibold text-gray-600">
      我
    </div>
  );
}

function MessageRow({ m }: { m: ChatMsg }) {
  const [copied, setCopied] = useState(false);
  const isUser = m.role === "user";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // 剪贴板不可用时静默
    }
  };

  return (
    <div className={`group flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      {isUser ? <UserAvatar /> : <AssistantAvatar />}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
          isUser ? "rounded-tr-sm bg-blue-600 text-white" : "rounded-tl-sm border border-gray-200 bg-surface"
        }`}
      >
        {!isUser && m.content ? (
          <MarkdownBody content={m.content} />
        ) : m.content ? (
          <div className="whitespace-pre-wrap text-sm">{m.content}</div>
        ) : null}
        {!isUser && m.error && <div className="text-sm text-red-600">{m.error}</div>}
        {!isUser && <CitationsBlock citations={m.citations ?? []} />}
        {!isUser && <ToolCallList toolCalls={m.toolCalls ?? []} />}
      </div>
      {!isUser && m.content && (
        <button
          onClick={() => void copy()}
          className="flex h-7 w-7 shrink-0 items-center justify-center self-center rounded-md text-gray-300 opacity-0 transition-opacity hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100"
          title={copied ? "已复制" : "复制回答"}
        >
          <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

export default function ChatPage() {
  const { userId, sessions, refreshSessions } = useSession();
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [history, setHistory] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const { state, send, stop } = useChatStream({
    onDone: (e) => {
      setHistory((msgs) => [...msgs, { role: "assistant", content: state.answer, citations: e.citations, toolCalls: e.tool_calls }]);
      setActiveSessionId(e.session_id);
      void refreshSessions();
    },
    onError: (msg) => {
      setHistory((msgs) => [...msgs, { role: "assistant", content: "", error: msg }]);
    },
  });

  const loadingSession = useCallback(async (sessionId: number) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const raw = await listMessages(sessionId);
      const msgs: ChatMsg[] = raw
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m: MessageOut) => {
          const cit = m.citations as { citations?: Citation[]; tool_calls?: ToolCallRecord[] } | null;
          return {
            role: m.role as "user" | "assistant",
            content: m.content,
            citations: cit?.citations,
            toolCalls: cit?.tool_calls,
          };
        });
      setHistory(msgs);
      setActiveSessionId(sessionId);
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : String(e));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const submit = (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || state.running) return;
    setHistory((msgs) => [...msgs, { role: "user", content: message }]);
    setInput("");
    setHistoryError(null);
    void send(message, activeSessionId, userId);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const liveCitations = state.retrieval?.chunks ?? state.done?.citations ?? [];
  const liveToolCalls = state.toolEnds.map((t) => ({
    tool: t.tool,
    success: t.success,
    latency_ms: t.latency_ms,
    error: t.error ?? undefined,
  }));

  return (
    <div className="flex h-full gap-4">
      {/* 会话列表 */}
      <div className="flex w-60 shrink-0 flex-col">
        <Card
          title="会话列表"
          className="h-full"
          actions={
            <IconButton onClick={() => void refreshSessions()} title="刷新">
              <Icon name="refresh" className="h-4 w-4" />
            </IconButton>
          }
        >
          <div className="space-y-1">
            <button
              onClick={() => {
                setActiveSessionId(null);
                setHistory([]);
              }}
              className={`flex w-full items-center gap-1.5 rounded-lg px-3 py-2 text-left text-sm ${
                activeSessionId === null ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Icon name="plus" className="h-3.5 w-3.5" />
              新对话
            </button>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => void loadingSession(s.id)}
                className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm ${
                  activeSessionId === s.id ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
                }`}
                title={s.title ?? `会话 #${s.id}`}
              >
                {s.title ?? `会话 #${s.id}`}
              </button>
            ))}
            {sessions.length === 0 && <EmptyState text="暂无会话" />}
          </div>
        </Card>
      </div>

      {/* 对话区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Card className="flex h-full flex-col" title={activeSessionId ? `会话 #${activeSessionId}` : "新对话"}>
          <div className="min-h-0 flex-1 space-y-4 overflow-auto pb-2">
            {historyLoading && <SkeletonLines lines={4} />}
            {historyError && <ErrorAlert message={historyError} onRetry={() => activeSessionId && void loadingSession(activeSessionId)} />}
            {!historyLoading && history.length === 0 && !state.running && (
              <EmptyState text="开始对话" hint="可从下方示例问题开始" />
            )}
            {history.map((m, i) => (
              <MessageRow key={i} m={m} />
            ))}
            {/* 流式中的实时内容 */}
            {state.running && (
              <div className="flex gap-2.5">
                <AssistantAvatar />
                <div className="min-w-0 max-w-[80%] rounded-2xl rounded-tl-sm border border-gray-200 bg-surface px-4 py-2.5">
                  {state.answer ? (
                    <>
                      <MarkdownBody content={state.answer} />
                      <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse rounded bg-blue-600 align-text-bottom" />
                    </>
                  ) : (
                    <TypingDots />
                  )}
                  {state.retrieval && <CitationsBlock citations={liveCitations} />}
                  <ToolCallList toolCalls={liveToolCalls} />
                </div>
              </div>
            )}
            {state.error && !state.running && (
              <ErrorAlert message={state.error} onRetry={() => setHistoryError(null)} />
            )}
            <div ref={bottomRef} />
          </div>

          {/* 输入区 */}
          <div className="mt-2 border-t border-gray-100 pt-3">
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
                placeholder="输入问题，Enter 发送"
                className="h-10 flex-1 rounded-lg border border-gray-300 px-3 text-sm outline-none focus:border-blue-500"
              />
              {state.running ? (
                <Button variant="outline" onClick={stop}>
                  <Icon name="stop" className="h-3.5 w-3.5" />
                  停止
                </Button>
              ) : (
                <Button onClick={() => submit()} disabled={!input.trim()}>
                  发送
                </Button>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

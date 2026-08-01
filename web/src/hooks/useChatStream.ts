/**
 * 对话流 hook: 消费 /chat/stream SSE 事件并分发到各面板.
 * 事件类型(对齐后端 chat_service.stream_events):
 *   retrieval / progress / tool_start / tool_end / token / done / error / heartbeat
 */

import { useCallback, useRef, useState } from "react";
import { chatStream } from "../api/endpoints";
import { parseSSE, type SSEEvent } from "../api/sse";
import type {
  DoneEvent,
  ErrorEvent,
  ProgressEvent,
  RetrievalEvent,
  ToolEndEvent,
  ToolStartEvent,
} from "../types/api";

export interface StreamState {
  running: boolean;
  answer: string;
  retrieval: RetrievalEvent | null;
  progress: ProgressEvent | null;
  toolStarts: ToolStartEvent[];
  toolEnds: ToolEndEvent[];
  done: DoneEvent | null;
  error: string | null;
  rawEvents: SSEEvent[];
  tokenCount: number;
}

export interface StreamHandlers {
  onRetrieval?: (e: RetrievalEvent) => void;
  onProgress?: (e: ProgressEvent) => void;
  onToolStart?: (e: ToolStartEvent) => void;
  onToolEnd?: (e: ToolEndEvent) => void;
  onToken?: (delta: string, total: string) => void;
  onDone?: (e: DoneEvent) => void;
  onError?: (message: string) => void;
  onRaw?: (e: SSEEvent) => void;
}

export function useChatStream(handlers: StreamHandlers = {}) {
  const [state, setState] = useState<StreamState>({
    running: false,
    answer: "",
    retrieval: null,
    progress: null,
    toolStarts: [],
    toolEnds: [],
    done: null,
    error: null,
    rawEvents: [],
    tokenCount: 0,
  });
  const abortRef = useRef<AbortController | null>(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const send = useCallback(
    async (message: string, sessionId: number | null, userId: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState((s) => ({
        ...s,
        running: true,
        answer: "",
        retrieval: null,
        progress: null,
        toolStarts: [],
        toolEnds: [],
        done: null,
        error: null,
        rawEvents: [],
        tokenCount: 0,
      }));

      try {
        const resp = await chatStream({
          session_id: sessionId,
          message,
          user_id: userId,
        });
        let total = "";
        for await (const ev of parseSSE(resp)) {
          if (controller.signal.aborted) break;
          setState((s) => ({ ...s, rawEvents: [...s.rawEvents, ev] }));
          handlersRef.current.onRaw?.(ev);
          switch (ev.event) {
            case "retrieval":
              setState((s) => ({ ...s, retrieval: ev.data as RetrievalEvent }));
              handlersRef.current.onRetrieval?.(ev.data as RetrievalEvent);
              break;
            case "progress":
              setState((s) => ({ ...s, progress: ev.data as ProgressEvent }));
              handlersRef.current.onProgress?.(ev.data as ProgressEvent);
              break;
            case "tool_start":
              setState((s) => ({
                ...s,
                toolStarts: [...s.toolStarts, ev.data as ToolStartEvent],
              }));
              handlersRef.current.onToolStart?.(ev.data as ToolStartEvent);
              break;
            case "tool_end":
              setState((s) => ({
                ...s,
                toolEnds: [...s.toolEnds, ev.data as ToolEndEvent],
              }));
              handlersRef.current.onToolEnd?.(ev.data as ToolEndEvent);
              break;
            case "token": {
              const delta = (ev.data as { delta?: string }).delta ?? "";
              total += delta;
              setState((s) => ({ ...s, answer: total, tokenCount: s.tokenCount + 1 }));
              handlersRef.current.onToken?.(delta, total);
              break;
            }
            case "done":
              setState((s) => ({ ...s, done: ev.data as DoneEvent }));
              handlersRef.current.onDone?.(ev.data as DoneEvent);
              break;
            case "error":
              setState((s) => ({
                ...s,
                error: (ev.data as ErrorEvent).error ?? "未知错误",
              }));
              handlersRef.current.onError?.((ev.data as ErrorEvent).error ?? "未知错误");
              break;
            default:
              break;
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          const msg = e instanceof Error ? e.message : String(e);
          setState((s) => ({ ...s, error: msg }));
          handlersRef.current.onError?.(msg);
        }
      } finally {
        setState((s) => ({ ...s, running: false }));
      }
    },
    []
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({
      running: false,
      answer: "",
      retrieval: null,
      progress: null,
      toolStarts: [],
      toolEnds: [],
      done: null,
      error: null,
      rawEvents: [],
      tokenCount: 0,
    });
  }, []);

  return { state, send, stop, reset };
}

import type { ApiError } from '@/types';

/** API 基址：开发走 Vite 代理 /api → localhost:8000；可由 VITE_API_BASE 覆盖 */
const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api/v1';

export class HttpError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, payload: ApiError | string) {
    const err = typeof payload === 'string' ? { code: 'UNKNOWN', message: payload, details: null } : payload;
    super(err.message);
    this.status = status;
    this.code = err.code;
    this.details = err.details;
    this.name = 'HttpError';
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  /** 自定义请求头透传，例如 X-User-Id */
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/** 统一 JSON 请求：自动注入 JSON 头、解析响应、抛 HttpError */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, headers, ...rest } = options;
  const init: RequestInit = {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
  };
  if (body !== undefined && !(body instanceof FormData)) {
    init.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    init.body = body;
    // FormData 时让浏览器自动设置 boundary，移除手动 Content-Type
    delete (init.headers as Record<string, string>).Accept;
  }

  const res = await fetch(buildUrl(path, query), init);
  const contentType = res.headers.get('content-type') ?? '';

  if (!res.ok) {
    let payload: ApiError | string;
    if (contentType.includes('application/json')) {
      payload = (await res.json()) as ApiError;
    } else {
      payload = await res.text();
    }
    throw new HttpError(res.status, payload);
  }

  if (res.status === 204) return undefined as T;
  if (contentType.includes('application/json')) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

/**
 * SSE 流式对话：以 fetch ReadableStream 手动解析 `event:` / `data:` 帧。
 * 心跳 `: ping` 自动跳过。返回异步迭代器，逐事件 yield。
 * signal 用于用户停止时中断连接（AbortController）。
 */
export async function* streamSSE(
  path: string,
  body: unknown,
  headers?: Record<string, string>,
  signal?: AbortSignal,
): AsyncGenerator<{ event: string; data: unknown }> {
  const res = await fetch(`${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...headers,
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => 'SSE 连接失败');
    throw new HttpError(res.status, text);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let currentEvent = 'message';
  let dataLines: string[] = [];

  const flush = function* (): Generator<{ event: string; data: unknown }> {
    if (dataLines.length === 0) return;
    const raw = dataLines.join('\n');
    dataLines = [];
    let parsed: unknown = raw;
    try {
      parsed = JSON.parse(raw);
    } catch {
      /* 非 JSON 则保留原始字符串 */
    }
    yield { event: currentEvent, data: parsed };
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, idx).replace(/\r$/, '');
      buffer = buffer.slice(idx + 1);

      if (line === '') {
        // 空行 = 事件分界
        yield* flush();
        currentEvent = 'message';
        continue;
      }
      if (line.startsWith(':')) continue; // 心跳注释
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^ /, ''));
      }
    }
  }
  yield* flush();
}

/** 当前用户标识（记忆隔离用），缺省 anonymous，可在 appStore 中覆盖 */
export function getAuthHeaders(userId?: string): Record<string, string> {
  return userId ? { 'X-User-Id': userId } : {};
}

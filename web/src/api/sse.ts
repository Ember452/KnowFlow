/**
 * SSE 解析器: 后端 /chat/stream 为 POST 请求(EventSource 不支持), 用 fetch + ReadableStream
 * 手动解析 event:/data: 行. 心跳行(: 开头)跳过, data 优先按 JSON 解析, 失败回退字符串.
 */

export interface SSEEvent {
  event: string;
  data: unknown;
}

function parseData(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    return trimmed;
  }
}

/** 逐事件产出 SSE 事件(按空行分隔). */
export async function* parseSSE(resp: Response): AsyncGenerator<SSEEvent, void, void> {
  if (!resp.body) {
    throw new Error("响应无 body, 无法解析 SSE 流");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // 按行切分, 保留末尾未完成片段
    let idx: number;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, idx).replace(/\r$/, "");
      buffer = buffer.slice(idx + 1);

      if (line === "") {
        // 事件结束
        if (dataLines.length > 0) {
          yield { event: eventName, data: parseData(dataLines.join("\n")) };
        }
        eventName = "message";
        dataLines = [];
        continue;
      }
      if (line.startsWith(":")) continue; // 心跳/注释行
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
  }
  // 流结束: 处理残留
  if (buffer.trim() !== "" && dataLines.length > 0) {
    yield { event: eventName, data: parseData(dataLines.join("\n")) };
  }
}

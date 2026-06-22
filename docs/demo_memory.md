# 跨会话长期记忆演示脚本

> M6(P7) 验收演示: 会话 A 声明偏好 → 沉淀入长期 → 会话 B 提问召回并体现。
> 前置: docker compose 四件套就绪 + `.env` 配置 LLM API Key(召回注入需真实 LLM 生成回答)。

## 一键演示命令(PowerShell)

```powershell
# 1. 启动服务(另开终端执行)
uv run uvicorn knowflow.main:app --port 8000

# 2. 会话 A: 声明偏好(规则重要性 9 分, 自动写入短期记忆)
$sidA = (curl.exe -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"请记住我喜欢用 Markdown 写文档"}' | ConvertFrom-Json).session_id
Write-Host "会话 A id: $sidA"

# 3. 手动沉淀: 短期 → 长期(压缩后入库)
curl.exe -s -X POST http://localhost:8000/api/v1/memory/demo/sediment `
  -H "Content-Type: application/json" -d "{`"session_id`": $sidA}"

# 4. 查看长期记忆
curl.exe -s http://localhost:8000/api/v1/memory/demo

# 5. 会话 B(新会话): 提问触发召回, 回答应体现 Markdown 偏好
curl.exe -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"以后帮我写文档用什么格式好?"}'
```

## 预期输出

1. 步骤 3 返回 `{"saved": 1}`
2. 步骤 4 返回 1 条记忆: `content="请记住我喜欢用 Markdown 写文档"`, `importance=9.0`
3. 步骤 5 的回答体现偏好, 如"建议使用 Markdown 格式(根据您的偏好)"

## 原理说明(面试口径)

- **观察**: chat 链路将每轮 user/assistant 消息写入 Redis 短期记忆(`mem:short:{session_id}`, TTL 过期)
- **打分**: 重要性打分 = LLM 输出 0-10 JSON, 失败回退规则(偏好关键词 9 分 / 身份 6 分 / 寒暄 2 分)
- **沉淀**: 会话结束或每 5 轮, 筛选 importance ≥ 6.0 的用户消息, LLM 压缩出摘要后入库
  (long_term_memories: content + summary + importance + embedding)
- **召回**: 新会话提问时, 查询向量与记忆向量做余弦相似度, 结合重要性(0.2)与
  新鲜度(0.1, last_recall 衰减)排序, top_k=3 注入系统提示"用户记忆"段落

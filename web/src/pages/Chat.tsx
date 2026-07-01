import { useRef, useEffect, useState, useCallback } from 'react';
import { Row, Col, Card, Input, Button, Space, Typography, Collapse, Timeline, Tag, Alert, Divider, Tooltip, Skeleton } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import {
  SendOutlined,
  StopOutlined,
  RobotOutlined,
  UserOutlined,
  ToolOutlined,
  BranchesOutlined,
  FileSearchOutlined,
  LinkOutlined,
  PlusOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { useChatStore } from '@/stores/chatStore';
import { useAppStore } from '@/stores/appStore';
import { formatMs, relativeTime } from '@/lib/format';
import type { ChatMessage, Citation, ToolCall, RetrievalChunk } from '@/types';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

/** Markdown 自定义渲染：链接新窗口打开，其余元素样式由 .kf-md 统一控制 */
const mdComponents: Components = {
  a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
};

function ToolTimeline({ calls }: { calls: ToolCall[] }) {
  if (!calls.length) return null;
  return (
    <Timeline
      style={{ marginTop: 8 }}
      items={calls.map((c) => ({
        color: c.status === 'running' ? 'blue' : c.status === 'failed' ? 'red' : 'green',
        dot: c.status === 'running' ? <ToolOutlined spin /> : undefined,
        children: (
          <div style={{ fontSize: 13 }}>
            <Space>
              <Text code className="kf-mono">{c.tool}</Text>
              {c.status === 'running' && <Tag color="processing" style={{ borderRadius: 6, margin: 0 }}>运行中</Tag>}
              {c.status === 'success' && <Tag color="success" style={{ borderRadius: 6, margin: 0 }}>成功 {formatMs(c.latency_ms)}</Tag>}
            </Space>
            {c.result && (
              <Paragraph
                className="kf-mono"
                style={{ marginTop: 4, marginBottom: 0, fontSize: 12, color: 'var(--kf-text-3)', whiteSpace: 'pre-wrap' }}
                ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
              >
                {c.result}
              </Paragraph>
            )}
          </div>
        ),
      }))}
    />
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className="kf-bubble-in" style={{ display: 'flex', gap: 12, justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && (
        <div
          style={{
            width: 34, height: 34, borderRadius: 10, flexShrink: 0,
            background: 'linear-gradient(135deg, #c96442, #d97757)',
            color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 8px -2px rgba(201, 100, 66, 0.3)',
          }}
        >
          <RobotOutlined />
        </div>
      )}
      <div style={{ maxWidth: '68%', minWidth: 0 }}>
        {msg.delegated && (
          <Alert
            type="info"
            showIcon
            icon={<BranchesOutlined />}
            style={{ marginBottom: 8, borderRadius: 10 }}
            message={<span>已委派 Multi-Agent 并发执行（run #{msg.run_id}）</span>}
            description={msg.subtasks?.length ? `子任务：${msg.subtasks.join(' · ')}` : undefined}
          />
        )}
        <div
          className="kf-serif"
          style={{
            background: isUser ? 'linear-gradient(135deg, #c96442, #d97757)' : 'var(--kf-bubble-bg)',
            color: isUser ? '#fff' : 'var(--kf-text-1)',
            border: isUser ? 'none' : '1px solid var(--kf-bubble-border)',
            borderRadius: 14,
            borderBottomRightRadius: isUser ? 4 : 14,
            borderBottomLeftRadius: isUser ? 14 : 4,
            padding: '12px 16px',
            fontSize: 15,
            lineHeight: 1.7,
            boxShadow: isUser
              ? '0 2px 12px -3px rgba(201, 100, 66, 0.25)'
              : '0 1px 4px -1px rgba(61, 57, 41, 0.06), 0 1px 2px 0 rgba(61, 57, 41, 0.04)',
            wordBreak: 'break-word',
            transition: 'box-shadow 0.25s ease',
          }}
        >
          {isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
          ) : (
            <div className="kf-md">
              {msg.content ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                  {msg.content}
                </ReactMarkdown>
              ) : msg.streaming ? (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {msg.tool_calls && msg.tool_calls.length > 0 ? '正在调用工具…' : '正在思考…'}
                </Text>
              ) : null}
              {msg.streaming && msg.content && <span className="kf-caret" />}
            </div>
          )}
          {!isUser && msg.stopped && (
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--kf-text-3)' }}>⏹ 已停止生成</div>
          )}
        </div>
        {!isUser && <ToolTimeline calls={msg.tool_calls ?? []} />}
        {!isUser && msg.citations && msg.citations.length > 0 && (
          <Collapse
            ghost
            size="small"
            style={{ marginTop: 4 }}
            items={[{
              key: 'cite',
              label: <Space><FileSearchOutlined style={{ color: '#c96442' }} /><Text type="secondary" style={{ fontSize: 12 }}>引用 {msg.citations.length} 条</Text></Space>,
              children: msg.citations.map((c, i) => (
                <div key={i} style={{ fontSize: 13, marginBottom: 8, paddingLeft: 8, borderLeft: '2px solid var(--kf-quote-border)' }}>
                  <Space size={4}>
                    <Tag style={{ borderRadius: 6, margin: 0 }}>{c.source}</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>score {c.score.toFixed(2)}</Text>
                    {c.filename && <Text type="secondary" style={{ fontSize: 12 }}>{c.filename}</Text>}
                  </Space>
                  <div className="kf-serif" style={{ color: 'var(--kf-text-2)', marginTop: 2 }}>{c.content}</div>
                </div>
              )),
            }]}
          />
        )}
      </div>
      {isUser && (
        <div
          style={{
            width: 34, height: 34, borderRadius: 10, flexShrink: 0,
            background: 'linear-gradient(135deg, var(--kf-surface-tint), var(--kf-bubble-bg))',
            color: 'var(--kf-brand)', border: '1px solid var(--kf-bubble-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 1px 3px 0 rgba(61, 57, 41, 0.06)',
          }}
        >
          <UserOutlined />
        </div>
      )}
    </div>
  );
}

function SourcesPanel({ msg }: { msg?: ChatMessage }) {
  const retrieval = msg?.retrieval ?? [];
  const citations = msg?.citations ?? [];
  return (
    <Card title="来源与检索" bordered={false} size="small" style={{ height: '100%', overflow: 'auto' }}>
      {!msg ? (
        <EmptyState description="选择一条助手消息查看检索来源" />
      ) : (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>召回片段（{retrieval.length}）</Text>
          <Divider style={{ margin: '8px 0' }} />
          {retrieval.length === 0 && <Text type="secondary" style={{ fontSize: 13 }}>暂无召回</Text>}
          {retrieval.map((c: RetrievalChunk, i) => (
            <div key={i} style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--kf-surface-tint)', borderRadius: 8, border: '1px solid var(--kf-bubble-border)' }}>
              <Space size={4} style={{ marginBottom: 4 }}>
                <Tag color={c.source === 'rerank' ? 'orange' : c.source === 'graph_expand' ? 'purple' : 'default'} style={{ borderRadius: 6, margin: 0 }}>{c.source}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>{c.score.toFixed(3)}</Text>
              </Space>
              <div className="kf-serif" style={{ fontSize: 13, color: 'var(--kf-text-2)' }}>{c.content}</div>
            </div>
          ))}
          {citations.length > 0 && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>最终引用（{citations.length}）</Text>
              <div style={{ marginTop: 8 }}>
                {citations.map((c: Citation, i) => (
                  <Tag key={i} style={{ marginBottom: 6, borderRadius: 6 }}>
                    <LinkOutlined /> chunk#{c.chunk_id} · {c.score.toFixed(2)}
                  </Tag>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </Card>
  );
}

/** 会话历史侧边栏项 */
function SessionItemRow({
  title,
  time,
  active,
  onClick,
}: {
  title: string;
  time: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className="kf-session-item"
      style={{
        position: 'relative',
        padding: '10px 14px',
        cursor: 'pointer',
        borderLeft: active ? '3px solid #c96442' : '3px solid transparent',
        background: active ? 'rgba(201, 100, 66, 0.06)' : 'transparent',
        transition: 'all 0.2s ease',
      }}
    >
      <Space size={8} style={{ width: '100%' }}>
        <MessageOutlined style={{ color: active ? '#c96442' : '#9b9890', fontSize: 14, flexShrink: 0 }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="kf-serif" style={{ fontSize: 13.5, color: active ? 'var(--kf-text-1)' : 'var(--kf-text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {title}
          </div>
          <Text type="secondary" style={{ fontSize: 11 }}>{time}</Text>
        </div>
      </Space>
    </div>
  );
}

export default function Chat() {
  const {
    messages,
    isStreaming,
    error,
    sessionId,
    sessions,
    loadingSessions,
    loadingSession,
    send,
    stop,
    clear,
    loadSessions,
    loadSession,
  } = useChatStore();
  const userId = useAppStore((s) => s.userId);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  /** 用户是否停留在底部：手动上滚后暂停自动跟随 */
  const stickToBottom = useRef(true);
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');

  const scrollToBottom = useCallback((smooth: boolean) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }, []);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };

  // 进入页面加载历史会话列表
  useEffect(() => {
    loadSessions(userId);
  }, [userId, loadSessions]);

  // 流式期间用 auto 直跳，避免高频 token 触发 smooth 动画抖动
  useEffect(() => {
    if (stickToBottom.current) scrollToBottom(!isStreaming);
  }, [messages, isStreaming, scrollToBottom]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    stickToBottom.current = true;
    send(input.trim(), userId);
    setInput('');
  };

  const handleNewSession = () => {
    clear();
  };

  const handleSelectSession = (id: number) => {
    if (id === sessionId || isStreaming) return;
    stickToBottom.current = true;
    loadSession(id);
  };

  return (
    <div className="kf-fade-in" style={{ height: 'calc(100vh - 108px)', display: 'flex', flexDirection: 'column' }}>
      <PageHeader
        title="智能对话"
        subtitle="SSE 流式问答 · 检索增强 · 工具调用 · 多 Agent 编排 · 历史会话"
        extra={
          <Button icon={<PlusOutlined />} onClick={handleNewSession} disabled={isStreaming} className="kf-btn-glow" style={{ borderRadius: 10 }}>
            新建对话
          </Button>
        }
      />

      <Row gutter={16} style={{ flex: 1, minHeight: 0 }}>
        {/* 会话历史侧边栏 */}
        <Col xs={0} lg={5} xl={4} style={{ minHeight: 0 }}>
          <Card
            bordered={false}
            className="kf-glass"
            style={{ height: '100%', overflow: 'hidden', borderRadius: 14, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, overflow: 'auto', padding: 0 }}
          >
            <div style={{ padding: 12, borderBottom: '1px solid rgba(227, 224, 212, 0.6)' }}>
              <Text type="secondary" style={{ fontSize: 12, paddingLeft: 2 }}>历史会话（{sessions.length}）</Text>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              {loadingSessions && sessions.length === 0 && (
                <div style={{ padding: 16 }}>
                  <Skeleton active paragraph={{ rows: 4 }} />
                </div>
              )}
              {!loadingSessions && sessions.length === 0 && (
                <EmptyState description="暂无历史会话" />
              )}
              {loadingSession && (
                <div style={{ padding: 16 }}>
                  <Skeleton active paragraph={{ rows: 3 }} />
                </div>
              )}
              {sessions.map((s) => (
                <SessionItemRow
                  key={s.id}
                  title={s.title || `会话 #${s.id}`}
                  time={relativeTime(s.updated_at || s.created_at)}
                  active={s.id === sessionId}
                  onClick={() => handleSelectSession(s.id)}
                />
              ))}
            </div>
          </Card>
        </Col>

        {/* 消息区 + 输入 */}
        <Col xs={24} lg={13} xl={14} style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Card bordered={false} style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderRadius: 14 }} bodyStyle={{ flex: 1, minHeight: 0, padding: 0 }}>
            <div ref={scrollRef} onScroll={handleScroll} style={{ height: '100%', overflow: 'auto', padding: 16 }}>
            {loadingSession && messages.length === 0 && (
              <div style={{ padding: 16 }}>
                <Skeleton active paragraph={{ rows: 6 }} />
              </div>
            )}
            {!loadingSession && messages.length === 0 ? (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ textAlign: 'center', maxWidth: 420 }}>
                  <div className="kf-float" style={{ display: 'inline-block' }}>
                    <div
                      style={{
                        width: 64, height: 64, borderRadius: 18, margin: '0 auto',
                        background: 'linear-gradient(135deg, #c96442, #d97757)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 8px 24px -6px rgba(201, 100, 66, 0.35)',
                      }}
                    >
                      <RobotOutlined style={{ fontSize: 32, color: '#fff' }} />
                    </div>
                  </div>
                  <h2 className="kf-display" style={{ marginTop: 16, fontWeight: 400 }}>向 KnowFlow 提问</h2>
                  <Text type="secondary">基于 GraphRAG 检索企业知识库，支持工具调用与多 Agent 并发编排。</Text>
                  <div style={{ marginTop: 16, textAlign: 'left' }}>
                    {['员工年假制度是什么？', '对比产品 A/B/C 的价格并汇总', 'IT 单工的 SLA 要求？', '运营 SOP 里的故障上报流程'].map((s) => (
                      <Tag
                        key={s}
                        className="kf-card-hover"
                        style={{ margin: 4, borderRadius: 10, cursor: 'pointer', padding: '4px 12px' }}
                        onClick={() => setInput(s)}
                      >
                        {s}
                      </Tag>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <Space direction="vertical" size={20} style={{ width: '100%' }}>
                {messages.map((m) => <MessageBubble key={m.id} msg={m} />)}
              </Space>
            )}
            </div>
          </Card>

          {error && <Alert type="error" message={error} style={{ marginTop: 8, borderRadius: 10 }} closable />}

          <Card bordered={false} size="small" className="kf-glass" style={{ marginTop: 8, borderRadius: 14 }}>
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="输入问题，Enter 发送 · Shift+Enter 换行"
                autoSize={{ minRows: 1, maxRows: 5 }}
                className="kf-input-glow"
                style={{
                  borderRadius: '12px 0 0 12px',
                  background: 'var(--kf-input-bg)',
                  boxShadow: 'inset 0 1px 3px -1px rgba(61, 57, 41, 0.08)',
                }}
              />
              {isStreaming ? (
                <Button
                  danger
                  icon={<StopOutlined />}
                  onClick={stop}
                  className="kf-btn-glow"
                  style={{ borderRadius: '0 12px 12px 0' }}
                >
                  停止
                </Button>
              ) : (
                <Tooltip title="Enter 发送">
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="kf-btn-glow"
                    style={{
                      borderRadius: '0 12px 12px 0',
                      background: input.trim()
                        ? 'linear-gradient(135deg, #c96442, #d97757)'
                        : undefined,
                    }}
                  >
                    发送
                  </Button>
                </Tooltip>
              )}
            </Space.Compact>
          </Card>
        </Col>

        {/* 来源面板 */}
        <Col xs={0} lg={6} xl={6} style={{ minHeight: 0 }}>
          <SourcesPanel msg={lastAssistant} />
        </Col>
      </Row>
    </div>
  );
}

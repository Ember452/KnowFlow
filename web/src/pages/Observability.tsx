import { useState } from 'react';
import { Row, Col, Card, InputNumber, Button, Space, Tree, Typography, Modal, List, Drawer, Descriptions, message } from 'antd';
import type { DataNode } from 'antd/es/tree';
import {
  ReloadOutlined,
  SearchOutlined,
  PlayCircleOutlined,
  MessageOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import StatCard from '@/components/StatCard';
import { SpanTypeTag } from '@/components/StatusTag';
import { useAsync } from '@/hooks/useAsync';
import { tracesApi } from '@/api/traces';
import { formatMs, formatTime, formatPct } from '@/lib/format';
import type { TraceSpan, TraceStats, ReplayResult, SpanType } from '@/types';

const { Text } = Typography;

/** Span 类型固定展示顺序 */
const SPAN_TYPES: SpanType[] = ['root', 'agent_decision', 'tool_call', 'retrieval', 'memory_recall'];

/** 递归构建 antd Tree 节点：title = SpanTypeTag + name · latency */
function buildTreeNodes(spans: TraceSpan[]): DataNode[] {
  return spans.map((span) => ({
    key: span.id ?? span.trace_id,
    title: (
      <Space size={6} wrap>
        <SpanTypeTag type={span.span_type} />
        <span>{span.name}</span>
        <Text type="secondary" style={{ fontSize: 12 }}>
          · {formatMs(span.latency_ms)}
        </Text>
      </Space>
    ),
    children: span.children && span.children.length > 0 ? buildTreeNodes(span.children) : undefined,
  }));
}

/** 将 span 树展平为 id → span 映射，供点击选中查看详情 */
function flattenSpans(spans: TraceSpan[], acc: Map<string, TraceSpan>): void {
  for (const s of spans) {
    acc.set(String(s.id ?? s.trace_id), s);
    if (s.children && s.children.length > 0) flattenSpans(s.children, acc);
  }
}

export default function Observability() {
  const [msgApi, ctx] = message.useMessage();
  const stats = useAsync<TraceStats>(() => tracesApi.stats(24), []);

  // 会话 Trace 查询（按需触发，不随挂载自动加载）
  const [sessionId, setSessionId] = useState<number | null>(1);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceRoots, setTraceRoots] = useState<TraceSpan[] | null>(null);

  // Replay
  const [replayOpen, setReplayOpen] = useState(false);
  const [replay, setReplay] = useState<ReplayResult | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);

  // Span 详情抽屉
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null);
  const spanMap = new Map<string, TraceSpan>();
  if (traceRoots) flattenSpans(traceRoots, spanMap);

  const handleQuery = async () => {
    if (sessionId == null) return;
    setTraceLoading(true);
    try {
      const res = await tracesApi.get(sessionId);
      setTraceRoots(res.roots);
      if (res.roots.length === 0) msgApi.info('该会话无 Span 记录');
    } catch (e) {
      msgApi.error((e as Error).message);
      setTraceRoots(null);
    } finally {
      setTraceLoading(false);
    }
  };

  const handleReplay = async () => {
    if (sessionId == null) return;
    setReplayLoading(true);
    try {
      const res = await tracesApi.replay(sessionId);
      setReplay(res);
      setReplayOpen(true);
    } catch (e) {
      msgApi.error((e as Error).message);
    } finally {
      setReplayLoading(false);
    }
  };

  const bySpanType = stats.data?.by_span_type;
  const hasSpanBreakdown = bySpanType && Object.values(bySpanType).some((n) => n > 0);

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader
        title="可观测"
        subtitle="全链路 Trace 追踪 · Span 嵌套树 · Checkpoint 会话重放"
        extra={
          <Button icon={<ReloadOutlined />} onClick={stats.reload} loading={stats.loading}>
            刷新统计
          </Button>
        }
      />

      {/* 统计概览 */}
      {stats.error || (!stats.loading && !stats.data) ? (
        <Card bordered={false}>
          <EmptyState
            description="统计数据加载失败 · /traces/stats 不可用"
            actionText="重试"
            onAction={stats.reload}
          />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <StatCard
              title="对话数"
              value={stats.data?.total_conversations ?? 0}
              icon={<MessageOutlined />}
              loading={stats.loading}
            />
          </Col>
          <Col xs={12} md={6}>
            <StatCard
              title="平均耗时"
              value={stats.data?.avg_latency_ms ?? 0}
              suffix="ms"
              icon={<ClockCircleOutlined />}
              loading={stats.loading}
            />
          </Col>
          <Col xs={12} md={6}>
            <StatCard
              title="P95 耗时"
              value={stats.data?.p95_latency_ms ?? 0}
              suffix="ms"
              icon={<ThunderboltOutlined />}
              loading={stats.loading}
            />
          </Col>
          <Col xs={12} md={6}>
            <StatCard
              title="工具成功率"
              value={formatPct(stats.data?.tool_success_rate)}
              icon={<CheckCircleOutlined />}
              loading={stats.loading}
            />
          </Col>
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* 左：Span 类型分布 */}
        <Col xs={24} lg={10}>
          <Card
            title="Span 类型分布"
            bordered={false}
            style={{ height: '100%' }}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>近 {stats.data?.window_hours ?? 24}h</Text>}
          >
            {!hasSpanBreakdown ? (
              <EmptyState description="暂无 Span 类型分布数据" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {SPAN_TYPES.map((t) => {
                  const n = bySpanType![t] ?? 0;
                  if (!n) return null;
                  const total = Object.values(bySpanType!).reduce((s, v) => s + v, 0);
                  const pct = total > 0 ? Math.round((n / total) * 100) : 0;
                  return (
                    <div
                      key={t}
                      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                    >
                      <Space>
                        <SpanTypeTag type={t} />
                        <Text type="secondary" style={{ fontSize: 12 }}>{pct}%</Text>
                      </Space>
                      <Text>{n}</Text>
                    </div>
                  );
                })}
              </Space>
            )}
          </Card>
        </Col>

        {/* 右：会话 Trace 查询 */}
        <Col xs={24} lg={14}>
          <Card title="会话 Trace 查询" bordered={false} style={{ height: '100%' }}>
            <Space.Compact style={{ width: '100%' }}>
              <InputNumber
                value={sessionId}
                onChange={(v) => setSessionId(v)}
                placeholder="输入 session_id"
                min={1}
                style={{ flex: 1 }}
                onPressEnter={handleQuery}
              />
              <Button
                type="primary"
                loading={traceLoading}
                onClick={handleQuery}
                icon={<SearchOutlined />}
              >
                查询
              </Button>
            </Space.Compact>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 10 }}>
              加载该会话的完整 Span 嵌套树（root → agent_decision / tool_call / retrieval / memory_recall）
            </Text>
          </Card>
        </Col>
      </Row>

      {/* 底部：Trace 树 + 重放 */}
      <Card
        title="Trace 树"
        bordered={false}
        style={{ marginTop: 16 }}
        extra={
          traceRoots && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              session_id: {sessionId}
            </Text>
          )
        }
      >
        {traceLoading ? (
          <List loading />
        ) : !traceRoots || traceRoots.length === 0 ? (
          <EmptyState description="查询会话后展示完整 Span 嵌套树" />
        ) : (
          <Tree
            treeData={buildTreeNodes(traceRoots)}
            defaultExpandAll
            showLine
            blockNode
            selectable
            onSelect={(keys) => {
              const k = keys[0];
              if (typeof k === 'string') setSelectedSpan(spanMap.get(k) ?? null);
            }}
          />
        )}

        {traceRoots && traceRoots.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Button
              icon={<PlayCircleOutlined />}
              loading={replayLoading}
              onClick={handleReplay}
            >
              重放会话
            </Button>
          </div>
        )}
      </Card>

      {/* Span 详情抽屉 */}
      <Drawer
        title={selectedSpan ? `${selectedSpan.name} · span 详情` : 'span 详情'}
        width={520}
        open={selectedSpan !== null}
        onClose={() => setSelectedSpan(null)}
      >
        {selectedSpan && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Span ID">
                <Text code className="kf-mono" style={{ fontSize: 12 }}>{selectedSpan.id ?? selectedSpan.trace_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="类型"><SpanTypeTag type={selectedSpan.span_type} /></Descriptions.Item>
              <Descriptions.Item label="耗时">{formatMs(selectedSpan.latency_ms)}</Descriptions.Item>
              <Descriptions.Item label="开始时间">{formatTime(selectedSpan.started_at)}</Descriptions.Item>
              {selectedSpan.ended_at && (
                <Descriptions.Item label="结束时间">{formatTime(selectedSpan.ended_at)}</Descriptions.Item>
              )}
            </Descriptions>
            {selectedSpan.input !== undefined && (
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: 6 }}>输入</Text>
                <pre className="kf-mono" style={{ background: 'var(--kf-surface-tint)', padding: 12, borderRadius: 8, maxHeight: 240, overflow: 'auto', fontSize: 12, margin: 0 }}>
                  {typeof selectedSpan.input === 'string' ? selectedSpan.input : JSON.stringify(selectedSpan.input, null, 2)}
                </pre>
              </div>
            )}
            {selectedSpan.output !== undefined && (
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: 6 }}>输出</Text>
                <pre className="kf-mono" style={{ background: 'var(--kf-surface-tint)', padding: 12, borderRadius: 8, maxHeight: 240, overflow: 'auto', fontSize: 12, margin: 0 }}>
                  {typeof selectedSpan.output === 'string' ? selectedSpan.output : JSON.stringify(selectedSpan.output, null, 2)}
                </pre>
              </div>
            )}
          </Space>
        )}
      </Drawer>

      {/* Replay 结果 Modal */}
      <Modal
        title="会话重放"
        open={replayOpen}
        onCancel={() => setReplayOpen(false)}
        footer={null}
        width={760}
        destroyOnClose
      >
        {replay && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text type="secondary">Checkpoint ID：</Text>
              <Text code copyable>
                {replay.checkpoint_id}
              </Text>
            </div>
            <div>
              <Text type="secondary">Run ID：</Text>
              <Text>{replay.run_id}</Text>
              <Text type="secondary" style={{ marginLeft: 16 }}>Session ID：</Text>
              <Text>{replay.session_id}</Text>
            </div>
            <div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 6 }}>
                State：
              </Text>
              <pre
                className="kf-mono"
                style={{
                  background: 'var(--kf-surface-tint)',
                  padding: 12,
                  borderRadius: 8,
                  maxHeight: 240,
                  overflow: 'auto',
                  fontSize: 12,
                  margin: 0,
                }}
              >
                {JSON.stringify(replay.state, null, 2)}
              </pre>
            </div>
            <div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 6 }}>
                事件流（{replay.events.length}）：
              </Text>
              {replay.events.length === 0 ? (
                <EmptyState description="无事件" />
              ) : (
                <List
                  size="small"
                  bordered
                  dataSource={replay.events}
                  renderItem={(ev) => (
                    <List.Item>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Space size={6}>
                          <SpanTypeTag type={ev.span_type} />
                          <Text>{ev.name}</Text>
                        </Space>
                        <Space size={12}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTime(ev.started_at)}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatMs(ev.latency_ms)}
                          </Text>
                        </Space>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
}

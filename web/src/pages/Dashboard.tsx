import { Row, Col, Card, List, Tag, Button, Space, Typography, Alert } from 'antd';
import { AreaChart, Area, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer } from 'recharts';
import {
  RiseOutlined,
  NodeIndexOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  ForkOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  ReloadOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import PageHeader from '@/components/PageHeader';
import StatCard from '@/components/StatCard';
import EmptyState from '@/components/EmptyState';
import { useAsync } from '@/hooks/useAsync';
import { healthApi } from '@/api/health';
import { tracesApi } from '@/api/traces';
import type { DependencyStatus, TraceStats } from '@/types';

const { Text } = Typography;

/** 平台五大量化指标（来自 eval/reports 实测） */
// 注: 工具数/Token/耗时三项为“越小越好”, 下降是正面, 用 invertTrend 表达
const KPIS = [
  { title: 'GraphRAG Recall@10', value: 8, suffix: '%', trend: 8, icon: <RiseOutlined />, label: '相对 Hybrid baseline' },
  { title: '单轮可见工具数', value: -34.2, suffix: '%', trend: -34.2, icon: <NodeIndexOutlined />, label: '执行域隔离后', invertTrend: true },
  { title: 'Tool Schema Token', value: -32.6, suffix: '%', trend: -32.6, icon: <ApiOutlined />, label: '动态注入后', invertTrend: true },
  { title: 'Function Calling 准确率', value: 94.7, suffix: '%', icon: <CheckCircleFilled />, label: '工具调用正确率' },
  { title: '并发端到端耗时', value: -77.6, suffix: '%', trend: -77.6, icon: <ThunderboltOutlined />, label: '较串行下降', invertTrend: true },
];

/** 后端 by_hour.hour 形如 2026-08-08T10:00:00，取 HH:mm */
const hourLabel = (h: string) => (h.length >= 16 ? h.slice(11, 16) : h);

const MODULE_CARDS = [
  { title: '智能对话', desc: 'SSE 流式问答', path: '/chat', icon: '💬' },
  { title: '知识库', desc: '文档与检索', path: '/knowledge', icon: '📚' },
  { title: '检索调试', desc: 'GraphRAG 链路', path: '/retrieval', icon: '🔎' },
  { title: 'Agent 编排', desc: '多 Agent 委派', path: '/agents', icon: '🧩' },
  { title: '工具治理', desc: 'Skill 执行域', path: '/tools', icon: '🛠️' },
  { title: '可观测', desc: 'Trace 与 Replay', path: '/observability', icon: '📈' },
];

function isOk(v: DependencyStatus | 'ok' | 'error' | undefined): boolean {
  if (typeof v === 'string') return v === 'ok';
  return v?.status === 'ok';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const ready = useAsync(() => healthApi.readyz(), []);
  const stats = useAsync<TraceStats>(() => tracesApi.stats(24).catch(() => null as unknown as TraceStats), []);

  const deps: Array<[string, DependencyStatus | 'ok' | 'error' | undefined]> = ready.data
    ? Object.entries(ready.data.dependencies ?? {})
    : [];

  return (
    <div className="kf-fade-in">
      <PageHeader
        title="KnowFlow 总览"
        subtitle="可编排、可扩展的企业知识库 Agent 平台 · 六大核心能力"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { ready.reload(); stats.reload(); }}>
              刷新
            </Button>
            <Button type="primary" icon={<ForkOutlined />} onClick={() => navigate('/chat')}>
              开始对话
            </Button>
          </Space>
        }
      />

      {/* 五大量化指标 */}
      <Row gutter={[16, 16]}>
        {KPIS.map((k, i) => (
          <Col xs={12} md={8} lg={24 / 5} key={k.title}>
            <div className="kf-stagger-item" style={{ animationDelay: `${i * 0.06}s` }}>
              <StatCard
                title={k.title}
                value={k.value}
                suffix={k.suffix}
                trend={k.trend}
                trendLabel={k.label}
                icon={k.icon}
                invertTrend={k.invertTrend}
                loading={false}
              />
            </div>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* 服务健康 */}
        <Col xs={24} lg={12}>
          <Card title="服务健康" bordered={false} style={{ height: '100%' }} extra={<Text type="secondary" style={{ fontSize: 12 }}>GET /readyz</Text>}>
            {ready.loading ? (
              <List loading />
            ) : ready.error || !ready.data ? (
              <EmptyState description="后端未就绪或无法连接 · 请启动 uvicorn" actionText="重试" onAction={ready.reload} />
            ) : (
              <>
                <Alert
                  type={ready.data.status === 'ok' ? 'success' : 'error'}
                  message={ready.data.status === 'ok' ? '所有依赖就绪' : '存在异常依赖'}
                  showIcon
                  style={{ marginBottom: 12 }}
                />
                <List
                  dataSource={deps}
                  renderItem={([name, v]) => {
                    const ok = isOk(v);
                    const latency = typeof v === 'object' ? v.latency_ms : undefined;
                    return (
                      <List.Item>
                        <Space>
                          {ok ? (
                            <CheckCircleFilled style={{ color: '#788c5d' }} />
                          ) : (
                            <CloseCircleFilled style={{ color: '#d64545' }} />
                          )}
                          <Text strong>{name}</Text>
                        </Space>
                        <Space>
                          {latency !== undefined && <Text type="secondary" style={{ fontSize: 12 }}>{latency} ms</Text>}
                          <Tag color={ok ? 'success' : 'error'} style={{ borderRadius: 6, margin: 0 }}>
                            {ok ? 'ok' : 'error'}
                          </Tag>
                        </Space>
                      </List.Item>
                    );
                  }}
                />
              </>
            )}
          </Card>
        </Col>

        {/* 对话脉搏 */}
        <Col xs={24} lg={12}>
          <Card title="近 24h 对话脉搏" bordered={false} style={{ height: '100%' }} extra={<Text type="secondary" style={{ fontSize: 12 }}>GET /traces/stats</Text>}>
            {stats.loading ? (
              <List loading />
            ) : !stats.data ? (
              <EmptyState description="暂无可观测数据 · 后端 /traces/stats 不可用" />
            ) : (
              <Row gutter={[16, 16]}>
                <Col span={8}>
                  <StatCard title="对话数" value={stats.data.total_conversations} loading={false} />
                </Col>
                <Col span={8}>
                  <StatCard title="平均耗时" value={stats.data.avg_latency_ms} suffix="ms" loading={false} />
                </Col>
                <Col span={8}>
                  <StatCard title="工具成功率" value={(stats.data.tool_success_rate * 100).toFixed(1)} suffix="%" loading={false} />
                </Col>
                <Col span={24}>
                  <Text type="secondary" style={{ fontSize: 12 }}>P95 耗时 {stats.data.p95_latency_ms ?? '-'} ms · 检索调用 {stats.data.retrieval_count ?? 0} 次</Text>
                </Col>
                {stats.data.by_hour && stats.data.by_hour.length > 1 && (
                  <Col span={24} style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                      逐小时对话数趋势
                    </Text>
                    <ResponsiveContainer width="100%" height={110}>
                      <AreaChart data={stats.data.by_hour} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                        <defs>
                          <linearGradient id="kfHourGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#c96442" stopOpacity={0.25} />
                            <stop offset="100%" stopColor="#c96442" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <XAxis
                          dataKey="hour"
                          tickFormatter={hourLabel}
                          tick={{ fontSize: 10, fill: 'var(--kf-text-3)' }}
                          axisLine={false}
                          tickLine={false}
                          minTickGap={28}
                        />
                        <YAxis hide domain={[0, 'dataMax']} />
                        <RTooltip
                          formatter={(v: number | string) => [`${v} 次`, '对话数']}
                          labelFormatter={hourLabel}
                          contentStyle={{ borderRadius: 8, fontSize: 12 }}
                        />
                        <Area
                          type="monotone"
                          dataKey="conversations"
                          stroke="#c96442"
                          strokeWidth={1.6}
                          fill="url(#kfHourGrad)"
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </Col>
                )}
              </Row>
            )}
          </Card>
        </Col>
      </Row>

      {/* 模块快捷入口 */}
      <Card title="核心模块" bordered={false} style={{ marginTop: 16 }}>
        <Row gutter={[16, 16]}>
          {MODULE_CARDS.map((m, i) => (
            <Col xs={12} md={8} lg={4} key={m.title}>
              <div className="kf-stagger-item" style={{ animationDelay: `${0.3 + i * 0.05}s` }}>
                <Card
                  hoverable
                  size="small"
                  className="kf-card-hover"
                  onClick={() => navigate(m.path)}
                  style={{ textAlign: 'center', borderRadius: 12 }}
                >
                  <div style={{ fontSize: 26, marginBottom: 6 }}>{m.icon}</div>
                  <div style={{ fontWeight: 600 }}>{m.title}</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{m.desc}</Text>
                  <div style={{ marginTop: 6, color: '#c96442', fontSize: 12 }}>
                    进入 <ArrowRightOutlined />
                  </div>
                </Card>
              </div>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
}

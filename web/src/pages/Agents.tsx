import { useState } from 'react';
import { Row, Col, Card, Input, Button, Space, Typography, Table, Timeline, Tag, Alert, Descriptions, message } from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  BranchesOutlined,
  ThunderboltOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { RunStatusTag } from '@/components/StatusTag';
import { useAsync } from '@/hooks/useAsync';
import { agentsApi } from '@/api/agents';
import { formatMs, formatTime, relativeTime } from '@/lib/format';
import type { AgentRunDetail, CheckpointNode, AgentType, RunStatus } from '@/types';

const { Text } = Typography;

/** 将 checkpoint 节点按父子血缘排序（根 → 叶），支持分支 */
function buildLineage(nodes: CheckpointNode[]): CheckpointNode[] {
  const map = new Map(nodes.map((n) => [n.id, n]));
  const roots = nodes.filter((n) => !n.parent_checkpoint_id || !map.has(n.parent_checkpoint_id));
  const result: CheckpointNode[] = [];
  const visited = new Set<string>();
  const walk = (n: CheckpointNode) => {
    if (visited.has(n.id)) return;
    visited.add(n.id);
    result.push(n);
    nodes.filter((c) => c.parent_checkpoint_id === n.id).forEach(walk);
  };
  roots.forEach(walk);
  // 兜底：处理可能的环或孤立节点
  nodes.forEach((n) => {
    if (!visited.has(n.id)) result.push(n);
  });
  return result;
}

export default function Agents() {
  const [msgApi, ctx] = message.useMessage();
  const [runIdInput, setRunIdInput] = useState('1');
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const { data, loading, error, reload } = useAsync<AgentRunDetail | null>(
    async () => (activeRunId === null ? null : agentsApi.getRun(activeRunId)),
    [activeRunId],
  );

  const handleQuery = () => {
    const n = Number(runIdInput);
    if (!Number.isFinite(n) || n <= 0) {
      msgApi.error('请输入有效的 Run ID');
      return;
    }
    setActiveRunId(n);
  };

  const run = data?.run;
  const children = data?.children ?? [];
  const delegations = data?.delegations ?? [];
  const lineage = data?.checkpoint_lineage ? buildLineage(data.checkpoint_lineage) : [];

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader title="Agent 编排" subtitle="多 Agent 委派链 · Checkpoint 血缘 · 并发执行可视化" />

      <Alert
        type="info"
        showIcon
        icon={<ThunderboltOutlined />}
        style={{ marginBottom: 16, borderRadius: 10 }}
        message="子 Agent 并发执行，端到端耗时下降 77.6%"
        description="主 Agent 将复杂任务拆解并委派给多个子 Agent 并发处理，结合 Checkpoint 持久化实现状态回溯与故障恢复。"
      />

      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={runIdInput}
            onChange={(e) => setRunIdInput(e.target.value)}
            placeholder="输入 Run ID 查询编排详情"
            onPressEnter={handleQuery}
            prefix={<SearchOutlined />}
          />
          <Button type="primary" loading={activeRunId !== null && loading} onClick={handleQuery} icon={<BranchesOutlined />}>
            查询编排
          </Button>
        </Space.Compact>
      </Card>

      {activeRunId === null ? (
        <Card bordered={false}>
          <EmptyState description="输入 Run ID 查询 Agent 编排详情" />
        </Card>
      ) : loading && !data ? (
        <Card bordered={false} loading />
      ) : error && !data ? (
        <Card bordered={false}>
          <EmptyState description={error} actionText="重试" onAction={reload} />
        </Card>
      ) : data && run ? (
        <Row gutter={[16, 16]}>
          {/* 左侧：主 Run 信息 + 子 Agent 运行 */}
          <Col xs={24} lg={16}>
            <Card
              title="主 Run 信息"
              bordered={false}
              style={{ marginBottom: 16 }}
              extra={<Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={reload}>刷新</Button>}
            >
              <Descriptions column={{ xs: 1, sm: 2 }} size="small" bordered>
                <Descriptions.Item label="Run ID">{run.id}</Descriptions.Item>
                <Descriptions.Item label="类型">
                  <Tag color={run.agent_type === 'main' ? 'orange' : 'blue'} style={{ borderRadius: 6, margin: 0 }}>
                    {run.agent_type === 'main' ? '主 Agent' : '子 Agent'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="状态"><RunStatusTag status={run.status} /></Descriptions.Item>
                <Descriptions.Item label="会话 ID">{run.session_id}</Descriptions.Item>
                <Descriptions.Item label="开始时间">{formatTime(run.started_at)}</Descriptions.Item>
                <Descriptions.Item label="耗时">{formatMs(run.duration_ms)}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card
              title="子 Agent 运行"
              bordered={false}
              extra={<Tag style={{ borderRadius: 6 }}>{children.length} 个</Tag>}
            >
              <Table
                rowKey="id"
                size="small"
                dataSource={children}
                pagination={false}
                locale={{ emptyText: <EmptyState description="无子 Agent 运行" /> }}
                columns={[
                  { title: 'ID', dataIndex: 'id', width: 70 },
                  {
                    title: '类型', dataIndex: 'agent_type', width: 100,
                    render: (t: AgentType) => (
                      <Tag color={t === 'main' ? 'orange' : 'blue'} style={{ borderRadius: 6, margin: 0 }}>
                        {t === 'main' ? '主' : '子'}
                      </Tag>
                    ),
                  },
                  { title: '状态', dataIndex: 'status', width: 100, render: (s: RunStatus) => <RunStatusTag status={s} /> },
                  { title: '耗时', dataIndex: 'duration_ms', width: 90, render: formatMs },
                ]}
              />
            </Card>
          </Col>

          {/* 右侧：委派链 + Checkpoint 血缘 */}
          <Col xs={24} lg={8}>
            <Card
              title="委派链"
              bordered={false}
              style={{ marginBottom: 16 }}
              extra={<Tag style={{ borderRadius: 6 }}>{delegations.length} 条</Tag>}
            >
              <Table
                rowKey="id"
                size="small"
                dataSource={delegations}
                pagination={false}
                scroll={{ x: 560 }}
                locale={{ emptyText: <EmptyState description="无委派任务" /> }}
                columns={[
                  {
                    title: '任务', dataIndex: 'task', width: 160, ellipsis: true,
                    render: (v: string) => <Text className="kf-serif" style={{ fontSize: 13 }}>{v}</Text>,
                  },
                  { title: '状态', dataIndex: 'status', width: 90, render: (s: RunStatus) => <RunStatusTag status={s} /> },
                  {
                    title: '子 Run', dataIndex: 'child_run_id', width: 70,
                    render: (v?: number) => v ?? <Text type="secondary">-</Text>,
                  },
                  {
                    title: 'Checkpoint', dataIndex: 'checkpoint_id', width: 110, ellipsis: true,
                    render: (v?: string) => v
                      ? <Text code className="kf-mono" style={{ fontSize: 12 }}>{v.slice(0, 8)}</Text>
                      : <Text type="secondary">-</Text>,
                  },
                  {
                    title: '创建时间', dataIndex: 'created_at', width: 130,
                    render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{relativeTime(v)}</Text>,
                  },
                ]}
              />
            </Card>

            <Card
              title="Checkpoint 血缘"
              bordered={false}
              extra={<Tag style={{ borderRadius: 6 }}>{lineage.length} 个</Tag>}
            >
              {lineage.length === 0 ? (
                <EmptyState description="无 Checkpoint 记录" />
              ) : (
                <Timeline
                  items={lineage.map((node) => ({
                    color: '#c96442',
                    dot: <NodeIndexOutlined style={{ color: '#c96442', fontSize: 14 }} />,
                    children: (
                      <div>
                        <Space size={4}>
                          <Text code className="kf-mono" style={{ fontSize: 12 }}>{node.id.slice(0, 12)}</Text>
                          <Tag style={{ borderRadius: 6, margin: 0 }}>run #{node.agent_run_id}</Tag>
                        </Space>
                        <div style={{ marginTop: 2 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {node.parent_checkpoint_id ? `父 ${node.parent_checkpoint_id.slice(0, 12)}` : '根 Checkpoint'} · {relativeTime(node.created_at)}
                          </Text>
                        </div>
                      </div>
                    ),
                  }))}
                />
              )}
            </Card>
          </Col>
        </Row>
      ) : null}
    </div>
  );
}

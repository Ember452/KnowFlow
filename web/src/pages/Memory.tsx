import { Card, Table, Button, Typography, Tag, Progress, Popconfirm, message, Alert, Row, Col, Statistic } from 'antd';
import { ReloadOutlined, DeleteOutlined, ThunderboltOutlined, DatabaseOutlined, FireOutlined } from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { useAsync } from '@/hooks/useAsync';
import { useAppStore } from '@/stores/appStore';
import { memoryApi } from '@/api/memory';
import { relativeTime } from '@/lib/format';
import type { LongTermMemory } from '@/types';

const { Text, Paragraph } = Typography;

export default function Memory() {
  const [msgApi, ctx] = message.useMessage();
  const userId = useAppStore((s) => s.userId);
  const memories = useAsync(() => memoryApi.list(userId), [userId]);

  const handleSediment = async () => {
    try {
      const r = await memoryApi.sediment(userId);
      msgApi.success(r.message);
      memories.reload();
    } catch (e) {
      msgApi.error((e as Error).message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await memoryApi.remove(userId, id);
      msgApi.success('已删除');
      memories.reload();
    } catch (e) {
      msgApi.error((e as Error).message);
    }
  };

  const avgImportance = memories.data && memories.data.length
    ? memories.data.reduce((s, m) => s + m.importance, 0) / memories.data.length
    : 0;

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader
        title="记忆"
        subtitle={`长期记忆管理 · 当前用户 ${userId} · 跨会话语义召回 + LLM 压缩`}
        extra={
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleSediment} loading={memories.loading}>
            触发记忆沉淀
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        icon={<DatabaseOutlined />}
        style={{ marginBottom: 16, borderRadius: 10 }}
        message="记忆分层架构"
        description={
          <span>
            <Tag color="red" style={{ borderRadius: 6 }}>短期记忆 · Redis</Tag> 会话级 TTL 自动过期 ·
            <Tag color="blue" style={{ borderRadius: 6, marginLeft: 4 }}>长期记忆 · PostgreSQL</Tag> 跨会话持久化 + 向量召回 · 沉淀时按重要度筛选并 LLM 压缩注入
          </span>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={8}><Card bordered={false}><Statistic title="记忆总数" value={memories.data?.length ?? 0} /></Card></Col>
        <Col span={8}><Card bordered={false}><Statistic title="平均重要度" value={avgImportance.toFixed(2)} suffix="/ 1.0" /></Card></Col>
        <Col span={8}><Card bordered={false}><Statistic title="用户标识" value={userId} prefix={<FireOutlined style={{ color: '#c96442' }} />} /></Card></Col>
      </Row>

      <Card
        title="长期记忆列表"
        bordered={false}
        extra={<Button icon={<ReloadOutlined />} onClick={memories.reload}>刷新</Button>}
      >
        <Table
          rowKey="id"
          loading={memories.loading}
          dataSource={memories.data ?? []}
          locale={{ emptyText: <EmptyState description="暂无长期记忆" /> }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 70 },
            {
              title: '内容', dataIndex: 'content',
              render: (v: string) => <Paragraph className="kf-serif" style={{ margin: 0, fontSize: 13 }} ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}>{v}</Paragraph>,
            },
            {
              title: '摘要', dataIndex: 'summary', width: 220, ellipsis: true,
              render: (v?: string) => v ? <Text type="secondary" style={{ fontSize: 13 }}>{v}</Text> : <Text type="secondary">-</Text>,
            },
            {
              title: '重要度', dataIndex: 'importance', width: 150,
              render: (v: number) => (
                <div style={{ minWidth: 100 }}>
                  <Progress percent={Math.round(v * 100)} size="small" format={(p) => p + '%'} />
                </div>
              ),
            },
            { title: '会话', dataIndex: 'session_id', width: 80 },
            { title: '最近召回', dataIndex: 'last_recall', width: 110, render: relativeTime },
            {
              title: '操作', width: 80,
              render: (_: unknown, r: LongTermMemory) => (
                <Popconfirm title="删除该记忆？" onConfirm={() => handleDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

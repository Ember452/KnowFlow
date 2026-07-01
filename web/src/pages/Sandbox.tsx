import { useState } from 'react';
import { Card, InputNumber, Button, Space, Typography, Tag, Progress, Popconfirm, message, Alert, Row, Col, Table } from 'antd';
import { FolderOpenOutlined, DeleteOutlined, ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { useAsync } from '@/hooks/useAsync';
import { sandboxApi } from '@/api/sandbox';
import { formatBytes, relativeTime } from '@/lib/format';
import type { WorkspaceFile } from '@/types';

const { Text } = Typography;

/** 配额接近满的阈值（百分比） */
const QUOTA_WARN_PERCENT = 90;

export default function Sandbox() {
  const [msgApi, ctx] = message.useMessage();
  const [sessionId, setSessionId] = useState(1);
  const [activeSessionId, setActiveSessionId] = useState(1);
  const [clearing, setClearing] = useState(false);

  const files = useAsync(() => sandboxApi.files(activeSessionId), [activeSessionId]);
  const quota = useAsync(() => sandboxApi.quota(activeSessionId), [activeSessionId]);

  const handleView = () => {
    if (!sessionId || sessionId < 1) {
      msgApi.warning('请输入有效的会话 ID');
      return;
    }
    setActiveSessionId(sessionId);
  };

  const handleClear = async () => {
    setClearing(true);
    try {
      await sandboxApi.clear(activeSessionId);
      msgApi.success('工作区已清理');
      files.reload();
      quota.reload();
    } catch (e) {
      msgApi.error((e as Error).message);
    } finally {
      setClearing(false);
    }
  };

  const used = quota.data?.used ?? 0;
  const limit = quota.data?.limit ?? 0;
  const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const nearFull = percent >= QUOTA_WARN_PERCENT;

  // spilled 文件排在后面
  const sortedFiles = [...(files.data ?? [])].sort((a, b) => {
    const sa = a.spilled ? 1 : 0;
    const sb = b.spilled ? 1 : 0;
    return sa - sb;
  });

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader title="沙箱" subtitle="会话隔离工作区 · 工具结果卸载与引用替换" />

      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Space>
          <Text type="secondary">会话 ID</Text>
          <InputNumber min={1} value={sessionId} onChange={(v) => setSessionId(v ?? 1)} style={{ width: 140 }} />
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={handleView} loading={files.loading}>
            查看工作区
          </Button>
          <Text type="secondary" style={{ fontSize: 12 }}>当前查看：session {activeSessionId}</Text>
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        icon={<SafetyCertificateOutlined />}
        style={{ marginBottom: 16, borderRadius: 10 }}
        message="沙箱隔离机制"
        description="每个会话拥有独立工作区，工具执行结果超出上下文窗口时自动卸载为文件，通过引用替代表示"
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="配额使用" bordered={false}>
            {quota.loading ? (
              <Text type="secondary">加载中…</Text>
            ) : quota.error || !quota.data ? (
              <EmptyState description="暂无配额数据" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Progress
                  percent={percent}
                  status={nearFull ? 'exception' : 'normal'}
                  format={() => `${percent}%`}
                />
                <Text>
                  已用 <Text strong>{formatBytes(used)}</Text> / {formatBytes(limit)}
                </Text>
              </Space>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="工作区操作" bordered={false} style={{ height: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                清理将删除该会话工作区的全部文件，包括工具结果卸载产生的 spilled 文件，引用将失效。
              </Text>
              <Popconfirm
                title="清理该会话工作区？"
                description="将删除全部工作区文件，操作不可恢复"
                onConfirm={handleClear}
                okText="清理"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<DeleteOutlined />} loading={clearing} block>
                  清理工作区
                </Button>
              </Popconfirm>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card
        title="工作区文件"
        bordered={false}
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => { files.reload(); quota.reload(); }}>
            刷新
          </Button>
        }
      >
        <Table
          rowKey="path"
          loading={files.loading}
          dataSource={sortedFiles}
          locale={{ emptyText: <EmptyState description="工作区暂无文件" /> }}
          scroll={{ x: 820 }}
          columns={[
            {
              title: '路径', dataIndex: 'path', ellipsis: true,
              render: (v: string) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
            },
            { title: '名称', dataIndex: 'name', ellipsis: true },
            {
              title: '类型', dataIndex: 'type', width: 90,
              render: (t: WorkspaceFile['type']) => (
                <Tag color={t === 'dir' ? 'orange' : 'blue'} style={{ borderRadius: 6, margin: 0 }}>
                  {t}
                </Tag>
              ),
            },
            { title: '大小', dataIndex: 'size', width: 100, render: formatBytes },
            { title: '修改时间', dataIndex: 'modified', width: 120, render: relativeTime },
            {
              title: '标记', dataIndex: 'spilled', width: 110,
              render: (v?: boolean) => v ? (
                <Tag color="orange" style={{ borderRadius: 6, margin: 0 }}>工具卸载</Tag>
              ) : <Text type="secondary">-</Text>,
            },
          ]}
        />
      </Card>
    </div>
  );
}

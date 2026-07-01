import { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Upload, Button, Input, InputNumber, Space, Typography, Tag, Popconfirm, Tooltip, message } from 'antd';
import { InboxOutlined, SearchOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import PageHeader from '@/components/PageHeader';
import { DocStatusTag } from '@/components/StatusTag';
import EmptyState from '@/components/EmptyState';
import { useAsync } from '@/hooks/useAsync';
import { documentsApi } from '@/api/documents';
import { knowledgeApi } from '@/api/knowledge';
import { formatBytes, formatTime } from '@/lib/format';
import type { KnowDocument, SearchResponse, RetrievalSource } from '@/types';

const { Dragger } = Upload;
const { Text } = Typography;

const SOURCE_COLOR: Record<RetrievalSource, string> = {
  vector: 'blue',
  bm25: 'geekblue',
  hybrid: 'cyan',
  graph_expand: 'purple',
  rerank: 'orange',
};

/** 非终态（需要轮询）的文档状态 */
const ACTIVE_STATUS: KnowDocument['status'][] = ['indexing', 'reindexing'];

export default function Knowledge() {
  const [msgApi, ctx] = message.useMessage();
  const docs = useAsync(() => documentsApi.list(), []);
  const [query, setQuery] = useState('年假制度');
  const [topK, setTopK] = useState(5);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);

  const handleUpload = async (file: File) => {
    try {
      const r = await documentsApi.upload(file);
      msgApi.success(`${r.message}（doc_id=${r.doc_id}）`);
      docs.reload();
    } catch (e) {
      msgApi.error((e as Error).message);
    }
    return false;
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      setResult(await knowledgeApi.search(query.trim(), topK));
    } catch (e) {
      msgApi.error((e as Error).message);
    } finally {
      setSearching(false);
    }
  };

  // 存在索引中/重建中的文档时每 3s 轮询，直到全部到达终态（ready/failed）
  // 拆解 docs.data/reload 为局部变量，避免依赖整个 docs 对象导致 interval 反复重建
  const { data: docList, reload: reloadDocs } = docs;
  useEffect(() => {
    const hasActive = (docList ?? []).some((d) => ACTIVE_STATUS.includes(d.status));
    if (!hasActive) return;
    const timer = setInterval(() => reloadDocs(), 3000);
    return () => clearInterval(timer);
  }, [docList, reloadDocs]);

  return (
    <div className="kf-fade-in">
      {ctx}
      <PageHeader title="知识库" subtitle="文档上传 · 异步索引 · GraphRAG 检索测试" />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="文档列表" bordered={false} extra={<Button icon={<ReloadOutlined />} onClick={docs.reload}>刷新</Button>}>
            <Table
              rowKey="id"
              loading={docs.loading}
              dataSource={docs.data ?? []}
              locale={{ emptyText: <EmptyState description="暂无文档，上传开始索引" /> }}
              scroll={{ x: 760 }}
              columns={[
                { title: 'ID', dataIndex: 'id', width: 60 },
                {
                  title: '文件名',
                  dataIndex: 'filename',
                  ellipsis: true,
                  render: (v: string, r: KnowDocument) => (
                    <Space><Tag style={{ borderRadius: 6, margin: 0 }}>{r.file_type}</Tag>{v}</Space>
                  ),
                },
                { title: '状态', dataIndex: 'status', width: 100, render: (s: KnowDocument['status']) => <DocStatusTag status={s} /> },
                { title: '大小', dataIndex: 'size', width: 90, render: formatBytes },
                { title: '分块', dataIndex: 'chunk_count', width: 70 },
                { title: '实体', dataIndex: 'entity_count', width: 70, render: (v?: number) => v ?? '-' },
                { title: '创建', dataIndex: 'created_at', width: 150, render: formatTime },
                {
                  title: '操作', width: 120, render: (_: unknown, r: KnowDocument) => (
                    <Space>
                      <Tooltip title="重建索引">
                        <Button
                          size="small"
                          icon={<ReloadOutlined />}
                          onClick={async () => {
                            try {
                              const rj = await documentsApi.reindex(r.id);
                              msgApi.success(rj.message ?? '已入队重建');
                            } catch (e) {
                              msgApi.error((e as Error).message);
                            }
                            docs.reload();
                          }}
                        />
                      </Tooltip>
                      <Popconfirm
                        title="删除文档与索引？"
                        onConfirm={async () => {
                          try {
                            await documentsApi.remove(r.id);
                            msgApi.success('已删除');
                          } catch (e) {
                            msgApi.error((e as Error).message);
                          }
                          docs.reload();
                        }}
                      >
                        <Button size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="上传文档" bordered={false}>
            <Dragger accept=".pdf,.docx,.md,.txt" multiple={false} showUploadList={false} beforeUpload={handleUpload}>
              <p className="ant-upload-drag-icon"><InboxOutlined style={{ color: '#c96442', fontSize: 40 }} /></p>
              <p className="ant-upload-text">点击或拖拽上传</p>
              <p className="ant-upload-hint">PDF / DOCX / MD / TXT · ≤ 50MB · 入队异步索引</p>
            </Dragger>
            <div style={{ marginTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                索引流程：解析 → 分块 → Embedding → 实体关系抽取 → 入库（Milvus 向量 + PG 图谱 + BM25）
              </Text>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="检索测试" bordered={false} style={{ marginTop: 16 }}>
        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="检索查询" onPressEnter={handleSearch} prefix={<SearchOutlined />} />
          <InputNumber min={1} max={20} value={topK} onChange={(v) => setTopK(v ?? 5)} style={{ width: 110 }} addonBefore="top_k" />
          <Button type="primary" loading={searching} onClick={handleSearch}>检索</Button>
        </Space.Compact>
        {result ? (
          <>
            <Space style={{ marginBottom: 12 }}>
              <Tag style={{ borderRadius: 6, margin: 0 }}>耗时 {result.latency_ms} ms</Tag>
              {result.expanded && <Tag color="purple" style={{ borderRadius: 6 }}>已一跳扩展</Tag>}
              {result.entity_hits && result.entity_hits.length > 0 && (
                <Tag color="orange" style={{ borderRadius: 6 }}>命中实体 {result.entity_hits.length}</Tag>
              )}
            </Space>
            <Table
              rowKey="chunk_id"
              dataSource={result.chunks}
              pagination={{ pageSize: 5 }}
              columns={[
                { title: '#', dataIndex: 'chunk_id', width: 60 },
                { title: '来源', dataIndex: 'source', width: 120, render: (s: RetrievalSource) => <Tag color={SOURCE_COLOR[s]} style={{ borderRadius: 6, margin: 0 }}>{s}</Tag> },
                { title: '分数', dataIndex: 'score', width: 90, render: (v: number) => v.toFixed(3) },
                { title: '内容', dataIndex: 'content', render: (v: string) => <Text className="kf-serif" style={{ fontSize: 13 }}>{v}</Text> },
              ]}
            />
          </>
        ) : (
          <EmptyState description="输入查询后检索" />
        )}
      </Card>
    </div>
  );
}

import { Typography, Space } from 'antd';
import type { ReactNode } from 'react';

const { Title, Text } = Typography;

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  extra?: ReactNode;
  /** Newsreader 展示字体 */
  display?: boolean;
}

/** 统一页面标题区：展示标题 + 副标题 + 右侧操作槽 */
export default function PageHeader({ title, subtitle, extra, display = true }: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        flexWrap: 'wrap',
        gap: 12,
        marginBottom: 20,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <Title level={3} className={display ? 'kf-display' : ''} style={{ margin: 0, fontWeight: 400 }}>
          {title}
        </Title>
        {subtitle && (
          <Text type="secondary" style={{ fontSize: 13 }}>
            {subtitle}
          </Text>
        )}
      </div>
      {extra && <Space wrap>{extra}</Space>}
    </div>
  );
}

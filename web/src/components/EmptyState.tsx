import { Empty, Button } from 'antd';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  description?: string;
  image?: ReactNode;
  actionText?: string;
  onAction?: () => void;
}

/** 统一空状态 */
export default function EmptyState({ description = '暂无数据', actionText, onAction }: EmptyStateProps) {
  return (
    <Empty
      description={description}
      style={{ padding: '48px 0' }}
    >
      {actionText && onAction && (
        <Button type="primary" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </Empty>
  );
}

import { ConfigProvider, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { useAppStore } from '@/stores/appStore';
import { getThemeConfig } from '@/styles/theme';
import AppRoutes from '@/router';

export default function App() {
  const isDark = useAppStore((s) => s.isDark);
  return (
    <ConfigProvider locale={zhCN} theme={getThemeConfig(isDark)}>
      <AntdApp>
        <AppRoutes />
      </AntdApp>
    </ConfigProvider>
  );
}

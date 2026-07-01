import { Layout, Menu, Switch, Tooltip, Input, Space, Button } from 'antd';
import { useLocation, useNavigate, Outlet } from 'react-router-dom';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BulbOutlined,
  BulbFilled,
  GithubOutlined,
} from '@ant-design/icons';
import { useAppStore } from '@/stores/appStore';
import { NAV_ITEMS, NAV_GROUPS, findNavItem } from '@/config/nav';
import './MainLayout.css';

const { Sider, Header, Content } = Layout;

export default function MainLayout() {
  const isDark = useAppStore((s) => s.isDark);
  const toggleDark = useAppStore((s) => s.toggleDark);
  const collapsed = useAppStore((s) => s.collapsed);
  const toggleCollapsed = useAppStore((s) => s.toggleCollapsed);
  const userId = useAppStore((s) => s.userId);
  const setUserId = useAppStore((s) => s.setUserId);
  const location = useLocation();
  const navigate = useNavigate();
  const current = findNavItem(location.pathname);

  const menuItems = NAV_GROUPS.map((group) => ({
    key: group,
    type: 'group' as const,
    label: group,
    children: NAV_ITEMS.filter((i) => i.group === group).map((i) => ({
      key: i.key,
      icon: i.icon,
      label: i.label,
    })),
  }));

  return (
    <Layout style={{ minHeight: '100vh' }} data-theme={isDark ? 'dark' : 'light'}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={232}
        collapsedWidth={72}
        theme="light"
        className="kf-sider"
      >
        <div className="kf-logo">
          <span className="kf-logo-mark">K</span>
          {!collapsed && <span className="kf-logo-text kf-display">KnowFlow</span>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[current?.key ?? 'dashboard']}
          defaultOpenKeys={NAV_GROUPS}
          items={menuItems}
          onClick={({ key }) => {
            const item = NAV_ITEMS.find((i) => i.key === key);
            if (item) navigate(item.path);
          }}
        />
      </Sider>

      <Layout>
        <Header className="kf-header">
          <Space size="middle" align="center" style={{ minWidth: 0 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleCollapsed}
            />
            <div style={{ minWidth: 0 }}>
              <div className="kf-header-title kf-display">{current?.label ?? '总览'}</div>
              <div className="kf-header-desc">{current?.desc}</div>
            </div>
          </Space>

          <Space size="middle" align="center">
            <Tooltip title="记忆隔离用用户标识，透传 X-User-Id 头">
              <Input
                size="small"
                addonBefore="X-User-Id"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                style={{ width: 200 }}
              />
            </Tooltip>
            <Tooltip title={isDark ? '切换亮色' : '切换暗色'}>
              <Switch
                checked={isDark}
                onChange={toggleDark}
                checkedChildren={<BulbFilled />}
                unCheckedChildren={<BulbOutlined />}
              />
            </Tooltip>
            <Tooltip title="GitHub 仓库">
              <Button type="text" icon={<GithubOutlined />} href="https://github.com/Ember452/KnowFlow" target="_blank" />
            </Tooltip>
          </Space>
        </Header>

        <Content className="kf-content">
          <div key={location.pathname} className="kf-page-enter" style={{ height: '100%' }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}

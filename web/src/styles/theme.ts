import type { ThemeConfig } from 'antd';
import { theme as antdTheme } from 'antd';

/**
 * Claude 设计系统 token 映射到 AntD v5 主题。
 * 主色 terra-cotta #C96442(亮) / #D97757(暗)，暖色纸感背景、层叠阴影、8/12px 圆角。
 */
const FONT_SANS = "'Poppins', ui-sans-serif, system-ui, -apple-system, sans-serif";

const sharedComponents: ThemeConfig['components'] = {
  Layout: {
    siderBg: '#F5F4EE',
    headerBg: 'rgba(255, 255, 255, 0.82)',
    bodyBg: '#FAF9F5',
    headerHeight: 60,
  },
  Menu: {
    itemBg: 'transparent',
    itemSelectedBg: 'rgba(201, 100, 66, 0.12)',
    itemSelectedColor: '#934828',
    itemActiveBg: 'rgba(201, 100, 66, 0.08)',
    itemHoverBg: 'rgba(201, 100, 66, 0.06)',
    itemColor: '#535146',
    itemHoverColor: '#3D3929',
    itemBorderRadius: 8,
    iconSize: 17,
  },
  Card: {
    borderRadiusLG: 12,
    colorBorderSecondary: '#E3E0D4',
    paddingLG: 22,
    boxShadowTertiary: '0 2px 8px -2px rgba(61, 57, 41, 0.06), 0 1px 3px -1px rgba(61, 57, 41, 0.04)',
  },
  Button: {
    borderRadius: 8,
    controlHeight: 38,
    controlHeightLG: 44,
    primaryShadow: '0 2px 6px -1px rgba(201, 100, 66, 0.25), 0 1px 3px 0 rgba(0, 0, 0, 0.08)',
    fontWeight: 600,
  },
  Table: {
    borderRadius: 12,
    headerBg: '#F5F4EF',
    headerColor: '#535146',
    rowHoverBg: 'rgba(201, 100, 66, 0.04)',
    cellPaddingBlock: 12,
  },
  Tag: { borderRadiusSM: 6 },
  Tooltip: { borderRadius: 8 },
  Modal: { borderRadiusLG: 16 },
  Input: { borderRadius: 8, controlHeight: 38 },
  Select: { borderRadius: 8, controlHeight: 38 },
  Tabs: { itemColor: '#6E6D68', itemSelectedColor: '#934828', inkBarColor: '#C96442' },
  Progress: { defaultColor: '#C96442' },
  Statistic: { titleFontSize: 13, contentFontSize: 28 },
};

export function getThemeConfig(isDark: boolean): ThemeConfig {
  if (isDark) {
    return {
      algorithm: antdTheme.darkAlgorithm,
      token: {
        colorPrimary: '#D97757',
        colorBgBase: '#262624',
        colorTextBase: '#F1F1EF',
        colorBgContainer: '#2C2C2B',
        colorBgElevated: '#30302E',
        colorBgLayout: '#262624',
        colorBorder: '#3E3E38',
        colorBorderSecondary: '#4A4A43',
        colorText: '#F1F1EF',
        colorTextSecondary: '#B7B5A9',
        colorTextTertiary: '#908E84',
        colorSuccess: '#8CA06F',
        colorError: '#EF4444',
        colorWarning: '#D97757',
        colorInfo: '#D97757',
        borderRadius: 8,
        borderRadiusLG: 12,
        fontFamily: FONT_SANS,
        fontSize: 14,
        controlHeight: 38,
      },
      components: {
        ...sharedComponents,
        Layout: { ...sharedComponents?.Layout, siderBg: '#1F1E1D', headerBg: 'rgba(44, 44, 43, 0.82)', bodyBg: '#262624' },
        Menu: {
          ...sharedComponents?.Menu,
          itemSelectedBg: 'rgba(217, 119, 87, 0.18)',
          itemSelectedColor: '#F0C6B3',
          itemColor: '#B7B5A9',
          itemHoverColor: '#F1F1EF',
        },
        Card: { ...sharedComponents?.Card, colorBorderSecondary: '#3E3E38' },
        Table: { ...sharedComponents?.Table, headerBg: '#2C2C2B', headerColor: '#B7B5A9', rowHoverBg: 'rgba(217,119,87,0.06)' },
        Button: { ...sharedComponents?.Button, primaryShadow: '0 2px 6px -1px rgba(217, 119, 87, 0.3), 0 1px 3px 0 rgba(0, 0, 0, 0.12)' },
      },
    };
  }
  return {
    algorithm: antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: '#C96442',
      colorBgBase: '#FAF9F5',
      colorTextBase: '#3D3929',
      colorBgContainer: '#FFFFFF',
      colorBgElevated: '#FFFFFF',
      colorBgLayout: '#FAF9F5',
      colorBorder: '#DAD9D4',
      colorBorderSecondary: '#E3E0D4',
      colorText: '#3D3929',
      colorTextSecondary: '#6E6D68',
      colorTextTertiary: '#9B988C',
      colorSuccess: '#788C5D',
      colorError: '#D64545',
      colorWarning: '#C96442',
      colorInfo: '#C96442',
      borderRadius: 8,
      borderRadiusLG: 12,
      fontFamily: FONT_SANS,
      fontSize: 14,
      controlHeight: 38,
      controlHeightLG: 44,
    },
    components: sharedComponents,
  };
}

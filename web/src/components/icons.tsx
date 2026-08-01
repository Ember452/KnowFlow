/**
 * 内联 SVG 图标集(20 视口线性风格), 替代 emoji 导航与操作图标.
 * 不引入第三方图标库, 保持零依赖.
 */

import type { ReactNode } from "react";

export type IconName =
  | "chat"
  | "agent"
  | "report"
  | "knowledge"
  | "tools"
  | "memory"
  | "observability"
  | "eval"
  | "plus"
  | "copy"
  | "check"
  | "stop"
  | "refresh"
  | "trash"
  | "search"
  | "x"
  | "upload"
  | "download"
  | "sparkles"
  | "send"
  | "sun"
  | "moon";

const PATHS: Record<IconName, ReactNode> = {
  chat: (
    <>
      <path d="M4.5 6.5A1.5 1.5 0 0 1 6 5h8a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 14 13h-3.4l-3.3 2.3v-2.3H6a1.5 1.5 0 0 1-1.5-1.5v-5Z" />
      <circle cx="8" cy="9" r="0.8" fill="currentColor" stroke="none" />
      <circle cx="11.5" cy="9" r="0.8" fill="currentColor" stroke="none" />
    </>
  ),
  agent: (
    <>
      <rect x="6.5" y="6.5" width="7" height="7" rx="1.5" />
      <rect x="8.6" y="8.6" width="2.8" height="2.8" rx="0.75" />
      <path d="M8 4.5v2M12 4.5v2M8 13.5v2M12 13.5v2M4.5 8h2M4.5 12h2M13.5 8h2M13.5 12h2" />
    </>
  ),
  report: (
    <>
      <path d="M6.5 3.5h4.2l2.8 2.8v9.2a1.5 1.5 0 0 1-1.5 1.5h-5.5A1.5 1.5 0 0 1 5 15.5v-10.5A1.5 1.5 0 0 1 6.5 3.5Z" />
      <path d="M10.7 3.5v2.8h2.8" />
      <path d="M7.5 10.5h5M7.5 13h3" />
    </>
  ),
  knowledge: (
    <>
      <path d="M10 5.4C8.9 4.5 7.5 4 5.9 4H4.2v9.4h1.7c1.6 0 3 .5 4.1 1.3 1.1-.8 2.5-1.3 4.1-1.3h1.7V4h-1.7c-1.6 0-3 .5-4.1 1.4Z" />
      <path d="M10 5.4v9.3" />
    </>
  ),
  tools: (
    <>
      <path d="M4 6.5h6.5M13.5 6.5H16M4 13.5h3.5M10.5 13.5H16" />
      <circle cx="12" cy="6.5" r="1.5" />
      <circle cx="9" cy="13.5" r="1.5" />
    </>
  ),
  memory: (
    <>
      <ellipse cx="10" cy="5" rx="6.2" ry="2.4" />
      <path d="M3.8 5v4.8c0 1.3 2.8 2.4 6.2 2.4s6.2-1.1 6.2-2.4V5" />
      <path d="M3.8 9.8v4.8c0 1.3 2.8 2.4 6.2 2.4s6.2-1.1 6.2-2.4V9.8" />
    </>
  ),
  observability: (
    <>
      <path d="M4 16.5v-3M8 16.5v-6M12 16.5v-9M16 16.5v-5" />
      <path d="M3 16.5h14" />
    </>
  ),
  eval: (
    <>
      <circle cx="10" cy="10" r="6.8" />
      <circle cx="10" cy="10" r="3.8" />
      <circle cx="10" cy="10" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
  plus: <path d="M10 4.8v10.4M4.8 10h10.4" />,
  copy: (
    <>
      <rect x="7.5" y="7.5" width="8.5" height="8.5" rx="1.5" />
      <path d="M12.5 7.5v-1A1.5 1.5 0 0 0 11 5H5.5A1.5 1.5 0 0 0 4 6.5v5A1.5 1.5 0 0 0 5.5 13h2" />
    </>
  ),
  check: <path d="M4.5 10.5l3.5 3.5 7.5-8" />,
  stop: <rect x="6.3" y="6.3" width="7.4" height="7.4" rx="1.2" fill="currentColor" stroke="none" />,
  refresh: (
    <>
      <path d="M16.5 10a6.5 6.5 0 1 1-1.9-4.6" />
      <path d="M16.5 3.8v3.4h-3.4" />
    </>
  ),
  trash: (
    <>
      <path d="M5 6.5h10" />
      <path d="M8 6.5V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.5" />
      <path d="M6.5 6.5l.6 8.6a1.5 1.5 0 0 0 1.5 1.4h2.8a1.5 1.5 0 0 0 1.5-1.4l.6-8.6" />
      <path d="M8.8 9.8v3.4M11.2 9.8v3.4" />
    </>
  ),
  search: (
    <>
      <circle cx="9.2" cy="9.2" r="4.2" />
      <path d="M12.4 12.4L16 16" />
    </>
  ),
  x: <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" />,
  upload: (
    <>
      <path d="M10 12.5v-9" />
      <path d="M6.5 7L10 3.5 13.5 7" />
      <path d="M4 13.5v2A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5v-2" />
    </>
  ),
  download: (
    <>
      <path d="M10 3.5v9" />
      <path d="M6.5 9L10 12.5 13.5 9" />
      <path d="M4 13.5v2A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5v-2" />
    </>
  ),
  sparkles: (
    <>
      <path
        d="M10 3.5l.9 2.6a4 4 0 0 0 2.6 2.6l2.6.9-2.6.9a4 4 0 0 0-2.6 2.6l-.9 2.6-.9-2.6a4 4 0 0 0-2.6-2.6l-2.6-.9 2.6-.9a4 4 0 0 0 2.6-2.6l.9-2.6Z"
        fill="currentColor"
        stroke="none"
      />
      <path
        d="M16.5 12.5l.4 1.2a2 2 0 0 0 1.3 1.3l1.2.4-1.2.4a2 2 0 0 0-1.3 1.3l-.4 1.2-.4-1.2a2 2 0 0 0-1.3-1.3l-1.2-.4 1.2-.4a2 2 0 0 0 1.3-1.3l.4-1.2Z"
        fill="currentColor"
        stroke="none"
      />
    </>
  ),
  send: (
    <>
      <path d="M17.2 3.4 3.8 9.4l5.4 2.2 2.2 5.4 5.8-13.6Z" />
      <path d="M9.2 11.6l8-8" />
    </>
  ),
  sun: (
    <>
      <circle cx="10" cy="10" r="3.5" />
      <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.8 4.8l1.4 1.4M13.8 13.8l1.4 1.4M15.2 4.8l-1.4 1.4M6.2 13.8l-1.4 1.4" />
    </>
  ),
  moon: <path d="M16.3 12.1A6.8 6.8 0 1 1 9.9 5.7a5.7 5.7 0 0 0 6.4 6.4Z" />,
};

export function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

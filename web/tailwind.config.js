/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* 中性色走 CSS 变量: .dark 下由 index.css 整体翻转 */
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        gray: {
          50: "rgb(var(--c-gray-50) / <alpha-value>)",
          100: "rgb(var(--c-gray-100) / <alpha-value>)",
          200: "rgb(var(--c-gray-200) / <alpha-value>)",
          300: "rgb(var(--c-gray-300) / <alpha-value>)",
          400: "rgb(var(--c-gray-400) / <alpha-value>)",
          500: "rgb(var(--c-gray-500) / <alpha-value>)",
          600: "rgb(var(--c-gray-600) / <alpha-value>)",
          700: "rgb(var(--c-gray-700) / <alpha-value>)",
          800: "rgb(var(--c-gray-800) / <alpha-value>)",
          900: "rgb(var(--c-gray-900) / <alpha-value>)",
        },
        /* 彩色浅色调(状态底色)走 CSS 变量, 暗色下压暗 */
        blue: {
          50: "rgb(var(--c-blue-50) / <alpha-value>)",
          100: "rgb(var(--c-blue-100) / <alpha-value>)",
          200: "rgb(var(--c-blue-200) / <alpha-value>)",
          300: "rgb(var(--c-blue-300) / <alpha-value>)",
        },
        green: {
          50: "rgb(var(--c-green-50) / <alpha-value>)",
          100: "rgb(var(--c-green-100) / <alpha-value>)",
          200: "rgb(var(--c-green-200) / <alpha-value>)",
          300: "rgb(var(--c-green-300) / <alpha-value>)",
        },
        red: {
          50: "rgb(var(--c-red-50) / <alpha-value>)",
          100: "rgb(var(--c-red-100) / <alpha-value>)",
          200: "rgb(var(--c-red-200) / <alpha-value>)",
          300: "rgb(var(--c-red-300) / <alpha-value>)",
        },
        amber: {
          50: "rgb(var(--c-amber-50) / <alpha-value>)",
          100: "rgb(var(--c-amber-100) / <alpha-value>)",
          200: "rgb(var(--c-amber-200) / <alpha-value>)",
          300: "rgb(var(--c-amber-300) / <alpha-value>)",
        },
        indigo: {
          50: "rgb(var(--c-indigo-50) / <alpha-value>)",
          100: "rgb(var(--c-indigo-100) / <alpha-value>)",
          200: "rgb(var(--c-indigo-200) / <alpha-value>)",
          300: "rgb(var(--c-indigo-300) / <alpha-value>)",
        },
        purple: {
          50: "rgb(var(--c-purple-50) / <alpha-value>)",
          100: "rgb(var(--c-purple-100) / <alpha-value>)",
          200: "rgb(var(--c-purple-200) / <alpha-value>)",
          300: "rgb(var(--c-purple-300) / <alpha-value>)",
        },
        orange: {
          50: "rgb(var(--c-orange-50) / <alpha-value>)",
          100: "rgb(var(--c-orange-100) / <alpha-value>)",
          200: "rgb(var(--c-orange-200) / <alpha-value>)",
          300: "rgb(var(--c-orange-300) / <alpha-value>)",
        },
        yellow: {
          50: "rgb(var(--c-yellow-50) / <alpha-value>)",
          100: "rgb(var(--c-yellow-100) / <alpha-value>)",
          200: "rgb(var(--c-yellow-200) / <alpha-value>)",
          300: "rgb(var(--c-yellow-300) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "PingFang SC",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

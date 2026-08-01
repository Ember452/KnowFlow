import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 开发态: Vite dev server 代理 /api 到后端 8000; 生产态: 构建产物由 FastAPI 同源托管
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          reactflow: ["@xyflow/react"],
          vendor: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});

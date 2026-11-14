import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Khi chạy `npm run dev`, /api được chuyển tiếp sang api (mặc định localhost:8000) để cùng nguồn như nginx.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.VITE_API_PROXY || "http://localhost:8000" },
  },
});

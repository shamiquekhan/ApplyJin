import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend port — same for dev (proxy) and after deploy (same origin).
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
    },
  },
  preview: {
    port: 3000,
    host: true,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
    },
  },
});

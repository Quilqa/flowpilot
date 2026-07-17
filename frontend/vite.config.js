import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During dev, proxy API + WebSocket to the FastAPI server on :8321.
// In production the app is built to dist/ and served by FastAPI directly.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8321",
      "/ws": { target: "ws://localhost:8321", ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});

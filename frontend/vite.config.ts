import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite serves the SPA and proxies /api to FastAPI. Prod: FastAPI serves frontend/dist itself.
export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true },
});

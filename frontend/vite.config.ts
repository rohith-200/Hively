import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { mockApiPlugin } from "./mocks/server";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const mock = env.VITE_API_MODE !== "live";
  return {
    plugins: [react(), ...(mock ? [mockApiPlugin()] : [])],
    server: {
      port: 5173,
      strictPort: true,
      proxy: mock
        ? undefined
        : {
            "/api": {
              target: env.API_PROXY_TARGET || "http://127.0.0.1:8000",
              changeOrigin: true,
            },
          },
    },
    preview: {
      port: 4173,
      strictPort: true,
      proxy: mock
        ? undefined
        : {
            "/api": {
              target: env.API_PROXY_TARGET || "http://127.0.0.1:8000",
              changeOrigin: true,
            },
          },
    },
    build: { target: "es2022" },
  };
});

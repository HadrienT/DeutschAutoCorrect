/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // DAC_API_PORT comes from the environment (make exports it) or from the repo-root .env
  const apiPort = loadEnv(mode, "..", "DAC_").DAC_API_PORT ?? "8010";
  return {
    plugins: [react()],
    server: { port: 5173, proxy: { "/api": `http://localhost:${apiPort}` } },
    test: { environment: "node", include: ["src/**/*.test.ts"] },
  };
});

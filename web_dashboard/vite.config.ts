import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPorts = {
  registry: 8000,
  ingestion: 8001,
  anomaly: 8002,
  risk: 8003,
  iot: 8004,
};

const mkProxy = (port: number) => ({
  target: `http://127.0.0.1:${port}`,
  changeOrigin: true,
  rewrite: (path: string) => path.replace(/^\/api\/[^/]+/, ""),
});

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    host: "127.0.0.1",
    proxy: {
      "/api/registry": mkProxy(backendPorts.registry),
      "/api/ingestion": mkProxy(backendPorts.ingestion),
      "/api/anomaly": mkProxy(backendPorts.anomaly),
      "/api/risk": mkProxy(backendPorts.risk),
      "/api/iot": mkProxy(backendPorts.iot),
    },
  },
});

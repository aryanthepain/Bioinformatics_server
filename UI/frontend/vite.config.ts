import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Every request the browser makes to /api/... is forwarded to FastAPI.
// This means the frontend and backend look like one website during
// development, so there is no CORS configuration to get wrong.
//
// The target is 127.0.0.1 rather than "localhost" on purpose: on macOS,
// Node resolves "localhost" to the IPv6 address ::1 first, while uvicorn
// listens on IPv4 127.0.0.1 by default, which causes confusing
// "ECONNREFUSED" proxy errors.
const BACKEND_URL = process.env.VITE_BACKEND_URL || "https://protfunc.duckdns.org";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: BACKEND_URL,
        changeOrigin: true,
        secure: true,
      },
    },
  },
});

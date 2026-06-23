import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api and /ws to the FastAPI backend during local dev so the frontend
// can use same-origin relative URLs if desired.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});

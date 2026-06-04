import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy forwards /v1 to the FastAPI backend so the SPA and API share an origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});

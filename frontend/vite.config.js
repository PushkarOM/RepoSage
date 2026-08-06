import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Same-origin in dev: Vite serves the SPA at :5173 and proxies
  // /api/* to the FastAPI backend on :8000. The browser sees one
  // origin (localhost:5173), so httpOnly cookies set by /api/login
  // are sent on subsequent /api/* requests without any CORS dance.
  // In prod, nginx (or the platform's edge) does the same routing.
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

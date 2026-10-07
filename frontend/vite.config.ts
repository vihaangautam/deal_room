import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // VITE_API_URL etc. live in the repo-root .env (one file for both
  // backend and frontend local config, set up in Phase 0) rather than a
  // second frontend/.env — Vite only reads its own project root by
  // default, so without this every import.meta.env.VITE_* is undefined.
  envDir: path.resolve(__dirname, ".."),
  server: {
    port: 5173,
  },
})

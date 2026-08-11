import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  cacheDir: `${process.env.HOME}/.cache/atlas-flow-vite`,
  plugins: [react()],
  server: { port: 1420, strictPort: true, host: true },
});

import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.VITE_SERVER_URL || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/auth": target,
        "/characters": target,
        "/create-script": target,
        "/make-video": target,
        "/jobs": target,
        "/static": target,
        "/home": target,
      },
    },
  };
});

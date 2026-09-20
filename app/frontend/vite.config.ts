import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // A API escuta só em 127.0.0.1 e não tem autenticação enquanto o E1 não
    // trouxer o login. O proxy mantém tudo na mesma origem no desenvolvimento.
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});

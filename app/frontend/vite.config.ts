import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Data do build, na versão da barra lateral (src/versao.ts, 18/10/2026). Só no `npm run build`: no
// desenvolvimento a tela mostra "dev". No fuso de São Paulo, para o build da noite não virar o dia seguinte.
const dataDoBuild = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());

export default defineConfig(({ command }) => ({
  plugins: [react()],
  define: command === "build" ? { __DATA_DO_BUILD__: JSON.stringify(dataDoBuild) } : {},
  server: {
    port: 5173,
    // A API escuta só em 127.0.0.1 e não tem autenticação enquanto o E1 não
    // trouxer o login. O proxy mantém tudo na mesma origem no desenvolvimento.
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
    // Ponte temporária (23/09/2026): acesso remoto via túnel (ngrok) para a
    // Karine, no Canadá, ver o mesmo funil enquanto o E1 (nuvem/login) não
    // chega. Sem isto o Vite recusa qualquer domínio que não seja localhost —
    // proteção correta em produção, mas bloquearia o próprio túnel aqui.
    allowedHosts: true,
  },
}));

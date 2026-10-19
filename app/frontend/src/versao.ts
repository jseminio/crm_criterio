/** Versão mostrada na tela, ao lado do nome "Critério" — para conferir alinhamento entre quem está vendo a
 * tela e quem está olhando o código no GitHub (18/10/2026).
 *
 * Não há número escrito à mão (o "1.0" de antes nunca foi incrementado): a versão é a identidade do build,
 * `v2026.10.18 · a90b952`. A data é a do build desta tela, gravada pelo Vite (`vite.config.ts`); o commit é o
 * publicado, que a API lê do Coolify (`GET /api/versao`, `crm/versao.py`). No `npm run dev` não há data de
 * build: aparece "dev". */

declare const __DATA_DO_BUILD__: string | undefined;

/** "AAAA-MM-DD" do build desta tela; `null` no desenvolvimento e nos testes. */
export const DATA_DA_TELA: string | null = typeof __DATA_DO_BUILD__ === "string" ? __DATA_DO_BUILD__ : null;

export interface VersaoDaApi {
  commit: string | null;
  data_do_build: string | null;
}

const pontos = (data: string) => data.replaceAll("-", ".");
const brasileira = (data: string) => data.split("-").reverse().join("/");

/** O rótulo curto da barra lateral: `v2026.10.18 · a90b952`, `v2026.10.18` sem commit, `dev` sem build. */
export function rotuloDaVersao(dataDaTela: string | null, daApi: VersaoDaApi | null): string {
  const base = dataDaTela ? `v${pontos(dataDaTela)}` : "dev";
  return daApi?.commit ? `${base} · ${daApi.commit}` : base;
}

/** O detalhe, ao passar o mouse: de quando é cada parte e qual commit está no ar. */
export function detalheDaVersao(dataDaTela: string | null, daApi: VersaoDaApi | null): string {
  const tela = dataDaTela ? `build de ${brasileira(dataDaTela)}` : "desenvolvimento";
  const api = daApi === null ? "sem resposta" : daApi.data_do_build ? `build de ${brasileira(daApi.data_do_build)}` : "data desconhecida";
  const commit = daApi?.commit ? `commit ${daApi.commit}` : "commit desconhecido";
  return `Tela: ${tela} · API: ${api} · ${commit}`;
}

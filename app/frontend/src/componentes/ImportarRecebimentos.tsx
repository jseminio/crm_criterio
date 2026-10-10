/** Importar a planilha de recebimentos (10/10/2026, só o Administrador).
 *
 * Duas etapas: a **prévia** lê a planilha e mostra o que entra, o total por mês e cada linha que ficou
 * de fora com o motivo — nada é descartado em silêncio. **Confirmar** grava; reimportar um mês
 * substitui o que havia (as linhas antigas ficam guardadas, desligadas).
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ImportacaoDeRecebimentos, PreviaDeRecebimentos } from "../api/tipos";
import { dinheiro } from "../formato";
import { mesCurto } from "./MrrDaCarteira";
import { PainelLateral } from "./PainelLateral";

function emBase64(arquivo: File): Promise<string> {
  return new Promise((resolver, rejeitar) => {
    const leitor = new FileReader();
    leitor.onload = () => resolver(String(leitor.result).split(",", 2)[1] ?? "");
    leitor.onerror = () => rejeitar(new Error("não consegui ler o arquivo"));
    leitor.readAsDataURL(arquivo);
  });
}

export function ImportarRecebimentos({ aoImportar }: { aoImportar?: () => void }) {
  const [aberto, definirAberto] = useState(false);
  return (
    <>
      <button type="button" className="botao botao-secundario" onClick={() => definirAberto(true)}>
        Importar recebimentos
      </button>
      {aberto && <PainelDeImportacao aoFechar={() => definirAberto(false)} aoImportar={aoImportar} />}
    </>
  );
}

function PainelDeImportacao({ aoFechar, aoImportar }: { aoFechar: () => void; aoImportar?: () => void }) {
  const [arquivo, definirArquivo] = useState<{ nome: string; base64: string } | null>(null);
  const [previa, definirPrevia] = useState<PreviaDeRecebimentos | null>(null);
  const [feito, definirFeito] = useState<ImportacaoDeRecebimentos | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [ocupado, definirOcupado] = useState(false);

  async function escolher(f: File | undefined) {
    definirPrevia(null);
    definirFeito(null);
    definirErro(null);
    if (!f) return;
    definirOcupado(true);
    try {
      const base64 = await emBase64(f);
      definirArquivo({ nome: f.name, base64 });
      definirPrevia(await api.previaDeRecebimentos(f.name, base64));
    } catch (e) {
      definirErro(e instanceof ErroDaApi || e instanceof Error ? e.message : "não consegui ler a planilha");
    } finally {
      definirOcupado(false);
    }
  }

  async function confirmar() {
    if (!arquivo) return;
    definirOcupado(true);
    definirErro(null);
    try {
      definirFeito(await api.importarRecebimentos(arquivo.nome, arquivo.base64));
      aoImportar?.();
    } catch (e) {
      definirErro(e instanceof Error ? e.message : "a importação falhou");
    } finally {
      definirOcupado(false);
    }
  }

  const substitui = previa?.meses.filter((m) => m.substitui !== null) ?? [];

  return (
    <PainelLateral
      titulo="Importar recebimentos"
      subtitulo="Planilha .xlsx ou .csv: CNPJ (ou Grupo), Competência, Valor recebido e Data do recebimento"
      aoFechar={aoFechar}
      rodape={
        previa && !feito ? (
          <button type="button" className="botao botao-primario" disabled={ocupado || previa.reconhecidas === 0} onClick={confirmar}>
            {ocupado ? "Importando…" : substitui.length > 0 ? "Confirmar e substituir" : "Confirmar importação"}
          </button>
        ) : undefined
      }
    >
      <label className="campo">
        <span className="campo-rotulo">Planilha</span>
        <input type="file" accept=".xlsx,.csv" disabled={ocupado} onChange={(e) => escolher(e.target.files?.[0])} />
      </label>
      <p className="campo-ajuda">
        Uma linha por recebimento. Competência no formato mês/ano (10/2026). O CNPJ precisa estar cadastrado numa empresa do
        CRM; sem CNPJ, o nome do grupo ou da empresa serve, se não houver dois parecidos.
      </p>
      {ocupado && !previa && <p className="numero-estado">Lendo a planilha…</p>}
      {erro && <div className="estado estado-erro" role="alert"><p className="estado-texto">{erro}</p></div>}

      {previa && !feito && (
        <>
          <h3 className="numero-rotulo">Prévia: nada foi gravado ainda</h3>
          <p>
            <strong>{previa.reconhecidas}</strong> linha{previa.reconhecidas === 1 ? "" : "s"} reconhecida{previa.reconhecidas === 1 ? "" : "s"},{" "}
            total <strong>{dinheiro(previa.total)}</strong>.
          </p>
          <table className="tabela" aria-label="Meses da planilha">
            <thead><tr><th>Competência</th><th className="tabela-numero">Linhas</th><th className="tabela-numero">Total</th><th>O que acontece</th></tr></thead>
            <tbody>
              {previa.meses.map((m) => (
                <tr key={m.competencia}>
                  <td>{mesCurto(m.competencia)}</td>
                  <td className="tabela-numero">{m.linhas}</td>
                  <td className="tabela-numero">{dinheiro(m.total)}</td>
                  <td>{m.substitui !== null ? `⚠ substitui ${dinheiro(m.substitui)} já importados` : "mês novo"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {substitui.length > 0 && (
            <p className="recado" role="note">
              <strong>Atenção:</strong> {substitui.length === 1 ? "este mês já tinha" : "estes meses já tinham"} recebimentos importados.
              Confirmar substitui os valores; a importação anterior fica guardada no histórico.
            </p>
          )}
          {previa.problemas.length > 0 && (
            <>
              <h3 className="numero-rotulo">{previa.problemas.length} linha{previa.problemas.length === 1 ? "" : "s"} ficaram de fora</h3>
              <table className="tabela" aria-label="Linhas que ficaram de fora">
                <thead><tr><th className="tabela-numero">Linha</th><th>Motivo</th><th>O que a linha trazia</th></tr></thead>
                <tbody>
                  {previa.problemas.map((p) => (
                    <tr key={p.linha}><td className="tabela-numero">{p.linha}</td><td>{p.motivo}</td><td>{p.trecho}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="campo-ajuda">Corrija na planilha (ou cadastre o CNPJ na empresa) e escolha o arquivo de novo.</p>
            </>
          )}
        </>
      )}

      {feito && (
        <p className="recado" role="status">
          ✓ Importado: {feito.linhas} linha{feito.linhas === 1 ? "" : "s"}, {dinheiro(feito.total)}, competência{" "}
          {feito.competencias.map(mesCurto).join(", ")}.{feito.fora > 0 && ` ${feito.fora} ficaram de fora.`}
        </p>
      )}
    </PainelLateral>
  );
}

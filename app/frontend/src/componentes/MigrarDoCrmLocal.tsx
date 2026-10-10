/** Migrar do CRM local para a nuvem (decisões de Eduardo, 10/10/2026: o oficial passa a ser a nuvem).
 *
 * Só o Administrador. Escolher o backup baixado no CRM local mostra a **prévia**, sem gravar: tabela por tabela, o
 * que vem do local e o que fica da nuvem (usuários, perfis, integrações, manutenção, WhatsApp). Migrar substitui os
 * dados de negócio da nuvem, grava antes o backup da nuvem como estava e pede a palavra MIGRAR.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { PreviaDaMigracao } from "../api/tipos";
import { dataHora } from "../formato";

const ACAO: Record<string, string> = { substitui: "vem do local", preserva: "fica a da nuvem" };

export function MigrarDoCrmLocal() {
  const [arquivo, definirArquivo] = useState<File | null>(null);
  const [previa, definirPrevia] = useState<PreviaDaMigracao | null>(null);
  const [confirmacao, definirConfirmacao] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  async function escolher(f: File | null) {
    definirPrevia(null); definirFeito(null); definirErro(null); definirConfirmacao(""); definirArquivo(f);
    if (!f) return;
    definirOcupado(true);
    try {
      definirPrevia(await api.previaDaMigracao(f));
    } catch (e) {
      definirErro(e instanceof ErroDaApi ? e.message : "Não consegui ler o arquivo.");
    } finally {
      definirOcupado(false);
    }
  }

  async function migrar() {
    if (!arquivo) return;
    definirOcupado(true); definirErro(null);
    try {
      const r = await api.migrarDoCrmLocal(arquivo);
      definirFeito(`✓ Migrado: ${r.registros.toLocaleString("pt-BR")} registros do CRM local. O backup da nuvem como estava ficou guardado em ${r.backup_de_antes}.`);
      definirPrevia(null);
    } catch (e) {
      definirErro(e instanceof ErroDaApi ? e.message : "A migração falhou; nada foi gravado.");
    } finally {
      definirOcupado(false);
    }
  }

  const mudam = previa?.linhas.filter((l) => l.acao === "substitui" && (l.no_arquivo > 0 || l.na_nuvem > 0)) ?? [];
  const ficam = previa?.linhas.filter((l) => l.acao === "preserva") ?? [];

  return (
    <section className="numero" aria-labelledby="migrar-titulo">
      <h3 className="numero-rotulo" id="migrar-titulo">Migrar do CRM local</h3>
      <p>
        Traz para a nuvem os dados do CRM local: grupos, empresas, contatos, oportunidades, contratos, eventos, recebimentos,
        carteira, plano e fichas. <strong>Ficam os da nuvem:</strong> usuários e perfis, chaves das integrações, registro de
        manutenção e WhatsApp.
      </p>
      <p className="numero-detalhe">
        No CRM local, em Configurações › Backup, clique em “Baixar backup completo” e escolha o arquivo aqui. Primeiro vem a
        prévia; nada é gravado até você confirmar.
      </p>
      <label className="campo">
        <span className="campo-rotulo">Backup do CRM local (.zip)</span>
        <input type="file" accept=".zip" disabled={ocupado} onChange={(e) => void escolher(e.target.files?.[0] ?? null)} />
      </label>
      {ocupado && !previa && <p role="status">Lendo o arquivo…</p>}
      {erro && <p role="alert" className="estado-texto">{erro}</p>}

      {previa && (
        <>
          <p>
            Arquivo de {dataHora(previa.criado_em)} · <strong>{previa.registros_que_entram.toLocaleString("pt-BR")}</strong> registros
            vêm do local e substituem <strong>{previa.registros_que_saem.toLocaleString("pt-BR")}</strong> da nuvem.
          </p>
          {!previa.pode_migrar && (
            <div className="estado estado-erro" role="alert"><p className="estado-texto">Não dá para migrar: {previa.motivo}.</p></div>
          )}
          <table className="tabela" aria-label="Prévia da migração">
            <thead><tr><th>Tabela</th><th className="tabela-numero">No local</th><th className="tabela-numero">Na nuvem hoje</th><th>O que acontece</th></tr></thead>
            <tbody>
              {[...mudam, ...ficam].map((l) => (
                <tr key={l.tabela}><td>{l.tabela}</td><td className="tabela-numero">{l.no_arquivo}</td>
                  <td className="tabela-numero">{l.na_nuvem}</td><td>{ACAO[l.acao] ?? l.acao}</td></tr>
              ))}
            </tbody>
          </table>
          {previa.pode_migrar && (
            <>
              <p className="recado" role="note">
                <strong>Isto não tem volta pela tela:</strong> os dados de negócio da nuvem são substituídos pelos do local. Antes
                de gravar, a nuvem guarda o backup dela como está.
              </p>
              <label className="campo">
                <span className="campo-rotulo">Digite MIGRAR para confirmar</span>
                <input value={confirmacao} onChange={(e) => definirConfirmacao(e.target.value)} />
              </label>
              <button type="button" className="botao botao-primario" disabled={ocupado || confirmacao !== "MIGRAR"} onClick={() => void migrar()}>
                {ocupado ? "Migrando…" : "Migrar e substituir"}
              </button>
            </>
          )}
        </>
      )}
      {feito && <p role="status" className="recado">{feito}</p>}
    </section>
  );
}

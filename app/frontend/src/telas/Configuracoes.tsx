/** Configurações: backup lógico dos dados.
 *
 * Exporta e importa **os dados**, não o banco: o mesmo arquivo serve para levar
 * o CRM a outra máquina ou guardar uma cópia. Só funciona direto na máquina do
 * CRM — o servidor recusa pedidos que chegam por túnel.
 */

import { useState } from "react";
import { ErroDaApi, api } from "../api/cliente";
import type { ResumoDeBackup } from "../api/cliente";
import { dataHora } from "../formato";

function Tabelas({ resumo }: { resumo: ResumoDeBackup }) {
  return (
    <table className="tabela">
      <thead>
        <tr>
          <th>Tabela</th>
          <th>Registros</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(resumo.tabelas).map(([nome, n]) => (
          <tr key={nome}>
            <td>{nome}</td>
            <td>{n}</td>
          </tr>
        ))}
        <tr>
          <td>
            <strong>Total</strong>
          </td>
          <td>
            <strong>{resumo.total}</strong>
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export function Configuracoes() {
  const [arquivo, definirArquivo] = useState<File | null>(null);
  const [resumo, definirResumo] = useState<ResumoDeBackup | null>(null);
  const [substituir, definirSubstituir] = useState(false);
  const [confirmacao, definirConfirmacao] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const escolher = async (novo: File | null) => {
    definirArquivo(novo);
    definirResumo(null);
    definirErro(null);
    definirFeito(null);
    if (!novo) return;
    definirOcupado(true);
    try {
      definirResumo(await api.verificarBackup(novo));
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha inesperada.");
    } finally {
      definirOcupado(false);
    }
  };

  const importar = async () => {
    if (!arquivo) return;
    definirOcupado(true);
    definirErro(null);
    try {
      const r = await api.importarBackup(arquivo, substituir);
      definirFeito(`Importado: ${r.total} registros. Recarregue a página para ver os dados.`);
      definirConfirmacao("");
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha inesperada.");
    } finally {
      definirOcupado(false);
    }
  };

  const podeImportar = !!resumo && !ocupado && (!substituir || confirmacao === "SUBSTITUIR");

  return (
    <div className="configuracoes" style={{ display: "grid", gap: "var(--e4)", maxWidth: 720 }}>
      <section className="numero">
        <h3 className="numero-rotulo">Exportar</h3>
        <p>
          Baixa <strong>todos</strong> os dados em um único arquivo, com impressão digital para
          detectar corrupção. Não é um banco de dados: é o conteúdo, no mesmo padrão para
          exportar e importar.
        </p>
        <a className="botao botao-primario" href="/api/backup/exportar" download>
          Baixar backup completo
        </a>
        <p className="numero-detalhe">
          O arquivo tem todos os dados de cliente, sem criptografia. Guarde fora de pastas
          compartilhadas.
        </p>
      </section>

      <section className="numero">
        <h3 className="numero-rotulo">Importar</h3>
        <p>Escolha um arquivo de backup. Ele é conferido antes de qualquer alteração.</p>
        <label className="campo">
          <span className="campo-rotulo">Arquivo de backup (.zip)</span>
          <input
            type="file"
            accept=".zip"
            onChange={(e) => void escolher(e.target.files?.[0] ?? null)}
          />
        </label>

        {ocupado && !resumo && <p role="status">Conferindo o arquivo…</p>}
        {erro && (
          <p role="alert" className="estado-texto">
            {erro}
          </p>
        )}

        {resumo && (
          <>
            <p>
              ✓ Arquivo íntegro, gerado em {dataHora(resumo.criado_em)}.
            </p>
            <Tabelas resumo={resumo} />
            <label>
              <input
                type="checkbox"
                checked={substituir}
                onChange={(e) => definirSubstituir(e.target.checked)}
              />{" "}
              Substituir os dados atuais desta máquina
            </label>
            <p className="numero-detalhe">
              Sem marcar, a importação só funciona num CRM vazio. Substituir{" "}
              <strong>apaga o que existe hoje</strong> e não tem volta — baixe um backup antes.
            </p>
            {substituir && (
              <label className="campo">
                <span className="campo-rotulo">Digite SUBSTITUIR para confirmar</span>
                <input value={confirmacao} onChange={(e) => definirConfirmacao(e.target.value)} />
              </label>
            )}
            <button
              type="button"
              className="botao botao-primario"
              disabled={!podeImportar}
              onClick={() => void importar()}
            >
              Importar
            </button>
          </>
        )}
        {feito && <p role="status">{feito}</p>}
      </section>
    </div>
  );
}

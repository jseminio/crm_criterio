/** Configurações › Serviços e contratos › Contrato recorrente em Word (14/10/2026): a matriz com marcadores, o
 * próximo número CONT CCE RJ1, quem assina pela Critério e os padrões (vencimento e excedente do DP). */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ConfiguracaoDoDocumento, MatrizDoContrato as Matriz } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { dataHora } from "../formato";

export function MatrizDoContrato() {
  const { pode } = usarAcesso();
  const podeEditar = pode("configuracoes.servicos");
  const [matriz, definirMatriz] = useState<Matriz | null>(null);
  const [config, definirConfig] = useState<ConfiguracaoDoDocumento | null>(null);
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const carregar = () =>
    Promise.all([api.matrizDoContrato(), api.configuracaoDoDocumento()])
      .then(([m, c]) => {
        definirMatriz(m);
        definirConfig(c);
      })
      .catch((f) => definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao carregar a matriz do contrato."));

  useEffect(() => {
    void carregar();
  }, []);

  const executar = async (acao: () => Promise<unknown>, mensagem: string) => {
    definirOcupado(true);
    definirFalha(null);
    definirFeito(null);
    try {
      await acao();
      await carregar();
      definirFeito(mensagem);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirOcupado(false);
    }
  };

  if (!matriz || !config) return falha ? <p className="estado-texto estado-erro" role="alert">✗ {falha}</p> : null;
  const m = matriz.em_uso;
  const mudar = (campo: keyof ConfiguracaoDoDocumento, valor: string | number) => definirConfig({ ...config, [campo]: valor });

  return (
    <section aria-labelledby="matriz-contrato-titulo" style={{ marginTop: "var(--e4)" }}>
      <h3 className="reajuste-titulo" id="matriz-contrato-titulo">Contrato recorrente em Word</h3>
      <p className="campo-ajuda">
        A matriz é o Word do contrato com marcadores no lugar dos dados do cliente, como {"{{razao_social}}"} e {"{{valor_contabil}}"}.
        Ao gerar, o CRM troca cada marcador pelo valor. Matriz com marcador obrigatório faltando ou desconhecido fica gravada,
        mas não é usada.
      </p>
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      <p className="campo-ajuda">
        {m ? (
          <>
            Em uso: <strong>{m.nome_arquivo}</strong>, enviada por {m.enviada_por} em {dataHora(m.enviada_em)} ·{" "}
            <span className={`etiqueta etiqueta-${m.em_condicao ? "ganho" : "perda"}`}>{m.em_condicao ? "pronta" : "com erro"}</span>{" "}
            <button type="button" className="link-de-tabela" onClick={() => void api.baixarMatrizDoContrato(m.id)}>Baixar</button>
            {m.faltando.length > 0 && <span className="celula-fonte">Faltam: {m.faltando.map((n) => `{{${n}}}`).join(", ")}</span>}
            {m.desconhecidos.length > 0 && <span className="celula-fonte">Desconhecidos: {m.desconhecidos.map((n) => `{{${n}}}`).join(", ")}</span>}
          </>
        ) : (
          <span className="texto-espera">Nenhuma matriz ainda: o contrato recorrente não gera até subir o Word.</span>
        )}
      </p>
      {podeEditar && (
        <label className="botao botao-secundario" style={{ display: "inline-block", cursor: "pointer" }}>
          {ocupado ? "Enviando…" : m ? "Trocar a matriz (.docx)" : "Subir a matriz (.docx)"}
          <input type="file" accept=".docx" className="visualmente-oculto" disabled={ocupado} aria-label="Matriz do contrato recorrente"
            onChange={(e) => {
              const arquivo = e.target.files?.[0];
              e.target.value = "";
              if (arquivo) void executar(() => api.subirMatrizDoContrato(arquivo), `Matriz ${arquivo.name} enviada.`);
            }} />
        </label>
      )}

      <details style={{ margin: "var(--e3) 0" }}>
        <summary className="campo-ajuda" style={{ cursor: "pointer" }}>Lista de marcadores</summary>
        <ul className="campo-ajuda">
          {matriz.marcadores.map((x) => (
            <li key={x.nome}><code>{`{{${x.nome}}}`}</code>{x.obrigatorio && " (obrigatório)"}: {x.descricao}</li>
          ))}
        </ul>
      </details>

      <div className="filtros" style={{ alignItems: "flex-end" }}>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-proximo">Próximo número</label>
          <input id="ct-proximo" className="entrada" type="number" min={1} value={config.proximo_numero} disabled={!podeEditar}
            onChange={(e) => mudar("proximo_numero", Number(e.target.value))} />
          <span className="campo-ajuda" style={{ margin: 0 }}>Último usado: {config.ultimo_usado ?? "nenhum"}</span>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-signatario">Quem assina pela Critério</label>
          <input id="ct-signatario" className="entrada" value={config.signatario ?? ""} disabled={!podeEditar} maxLength={200}
            onChange={(e) => mudar("signatario", e.target.value)} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-cargo">Cargo</label>
          <input id="ct-cargo" className="entrada" value={config.cargo_signatario ?? ""} disabled={!podeEditar} maxLength={100}
            onChange={(e) => mudar("cargo_signatario", e.target.value)} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-cpf">CPF</label>
          <input id="ct-cpf" className="entrada" value={config.cpf_signatario ?? ""} disabled={!podeEditar} maxLength={14}
            onChange={(e) => mudar("cpf_signatario", e.target.value)} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-vencimento">Dia do vencimento</label>
          <input id="ct-vencimento" className="entrada" type="number" min={1} max={31} value={config.vencimento} disabled={!podeEditar}
            onChange={(e) => mudar("vencimento", Number(e.target.value))} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-excedente">Por funcionário além do quadro (R$)</label>
          <input id="ct-excedente" className="entrada" value={config.excedente_dp} disabled={!podeEditar}
            onChange={(e) => mudar("excedente_dp", e.target.value.replace(",", "."))} />
        </div>
        {podeEditar && (
          <button type="button" className="botao botao-secundario" disabled={ocupado}
            onClick={() => {
              const { ultimo_usado: _u, ...resto } = config;
              void executar(() => api.editarConfiguracaoDoDocumento(resto), "Configuração do contrato salva.");
            }}>
            Salvar configuração
          </button>
        )}
      </div>
    </section>
  );
}

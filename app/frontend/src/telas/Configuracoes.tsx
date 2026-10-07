/** Configurações, em abas (aprovado por Eduardo em 02/10/2026): perfis e acesso, metas, propostas,
 * grupos, conferência, histórico de alterações, backup e serviços pedidos. Cada aba só aparece para
 * quem pode vê-la.
 *
 * Backup lógico dos dados:
 *
 * Exporta e importa **os dados**, não o banco: o mesmo arquivo serve para levar
 * o CRM a outra máquina ou guardar uma cópia. Só funciona direto na máquina do
 * CRM — o servidor recusa pedidos que chegam por túnel.
 */

import { HistoricoDeAlteracoes } from "../componentes/HistoricoDeAlteracoes";
import { IntegracoesDoSistema } from "../componentes/IntegracoesDoSistema";
import { LinkDeArquivo } from "../componentes/LinkDeArquivo";
import { CadenciaDeReunioes } from "../componentes/CadenciaDeReunioes";
import { MetasDosIndicadores } from "../componentes/MetasDosIndicadores";
import { MatrizesDeProposta } from "../componentes/MatrizesDeProposta";
import { PerfisEAcesso } from "../componentes/PerfisEAcesso";
import { usarAcesso } from "../entrada";
import { Conferencia } from "./Conferencia";
import { Grupos } from "./Grupos";
import { useState } from "react";
import { ErroDaApi, api } from "../api/cliente";
import type { ResumoDeBackup } from "../api/cliente";
import type { Listas, PedidoDeServicoNovo } from "../api/tipos";
import { Carregando, Erro } from "../componentes/estados";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";

/** Todo "Outro" do catálogo de serviços (27/09/2026): o que o lead pediu e não
 * está na lista. Serve para decidir o que entra no catálogo; só leitura. */
function PedidosDeServicoNovo() {
  const { dados, carregando, erro, recarregar } = usarDados<PedidoDeServicoNovo[]>(
    () => api.pedidosDeServicoNovo(),
    [],
  );
  return (
    <section className="numero" aria-labelledby="pedidos-titulo">
      <h3 className="numero-rotulo" id="pedidos-titulo">
        Pedidos de serviço novo
      </h3>
      <p>
        Cada proposta ou lead em que o serviço escolhido foi "Outro", com a descrição do que o lead
        pediu. Quando um pedido se repetir, ele é candidato a entrar no catálogo.
      </p>
      {carregando && <Carregando rotulo="Carregando os pedidos" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!carregando && !erro && dados?.length === 0 && (
        <p className="numero-detalhe">
          Nenhum pedido ainda. Eles aparecem quando alguém escolhe "Outro serviço" no catálogo.
        </p>
      )}
      {!carregando && !erro && (dados?.length ?? 0) > 0 && (
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Quando</th>
              <th scope="col">Onde</th>
              <th scope="col">Nome</th>
              <th scope="col">O que o lead pediu</th>
            </tr>
          </thead>
          <tbody>
            {dados!.map((p) => (
              <tr key={`${p.onde}-${p.id}`}>
                <td>{dataHora(p.registrado_em)}</td>
                <td>{p.onde}</td>
                <td>{p.nome}</td>
                <td>{p.descricao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Tabelas({ resumo }: { resumo: ResumoDeBackup }) {
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const linhas = ordenar(Object.entries(resumo.tabelas), ordenacao, {
    tabela: ([nome]) => nome,
    registros: ([, n]) => n,
  });
  return (
    <table className="tabela">
      <thead>
        <tr>
          <ThOrdenavel coluna="tabela" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Tabela</ThOrdenavel>
          <ThOrdenavel coluna="registros" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Registros</ThOrdenavel>
        </tr>
      </thead>
      <tbody>
        {linhas.map(([nome, n]) => (
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

type Aba = "perfis" | "metas" | "propostas" | "integracoes" | "grupos" | "conferencia" | "historico" | "backup" | "servicos";

/** As abas, na ordem aprovada por Eduardo em 02/10/2026, com a funcionalidade que libera cada uma.
 * "Serviços pedidos" é só leitura e aparece para quem vê Configurações. */
const ABAS: { chave: Aba; rotulo: string; permissao: string | null }[] = [
  { chave: "perfis", rotulo: "Perfis e acesso", permissao: "configuracoes.perfis" },
  { chave: "metas", rotulo: "Metas", permissao: "configuracoes.metas" },
  { chave: "propostas", rotulo: "Propostas", permissao: "configuracoes.propostas" },
  // Chaves e integrações pela tela, sem nada no painel do servidor (aprovado por Eduardo em 07/10/2026).
  { chave: "integracoes", rotulo: "Integrações", permissao: "configuracoes.integracoes" },
  // Grupos e Conferência saíram do menu e viraram abas (aprovado por Eduardo em 02/10/2026).
  { chave: "grupos", rotulo: "Grupos", permissao: "grupos.ver" },
  { chave: "conferencia", rotulo: "Conferência", permissao: "conferencia.ver" },
  { chave: "historico", rotulo: "Histórico", permissao: "configuracoes.historico" },
  { chave: "backup", rotulo: "Backup", permissao: "configuracoes.backup" },
  { chave: "servicos", rotulo: "Serviços pedidos", permissao: null },
];
const CHAVE_DA_ABA = "crm.configuracoes.aba";

function abaGuardada(): Aba | null {
  try {
    return localStorage.getItem(CHAVE_DA_ABA) as Aba | null;
  } catch {
    return null;
  }
}

export function Configuracoes({ listas = null }: { listas?: Listas | null }) {
  const { pode } = usarAcesso();
  const visiveis = ABAS.filter((a) => a.permissao === null || pode(a.permissao));
  const [escolhida, definirEscolhida] = useState<Aba | null>(abaGuardada);
  const aba = visiveis.some((a) => a.chave === escolhida) ? escolhida! : visiveis[0].chave;
  const escolherAba = (nova: Aba) => {
    definirEscolhida(nova);
    try {
      localStorage.setItem(CHAVE_DA_ABA, nova);
    } catch {
      /* sem armazenamento: vale só nesta visita */
    }
  };
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
    // As abas usam a largura toda; os formulários ficam estreitos e as tabelas de Grupos e Conferência, largas.
    <div className={`configuracoes${aba === "grupos" || aba === "conferencia" ? "" : " configuracoes-estreita"}`} style={{ display: "grid", gap: "var(--e4)" }}>
      <div className="abas" role="tablist" aria-label="Seções de Configurações">
        {visiveis.map((a) => (
          <button key={a.chave} type="button" role="tab" className="aba" aria-selected={aba === a.chave} onClick={() => escolherAba(a.chave)}>
            {a.rotulo}
          </button>
        ))}
      </div>
      {aba === "perfis" && <PerfisEAcesso />}
      {aba === "metas" && (
        <>
          <MetasDosIndicadores />
          <CadenciaDeReunioes />
        </>
      )}
      {aba === "historico" && <HistoricoDeAlteracoes />}
      {aba === "backup" && (
      <>
      <section className="numero">
        <h3 className="numero-rotulo">Exportar</h3>
        <p>
          Baixa <strong>todos</strong> os dados em um único arquivo, com impressão digital para
          detectar corrupção. Não é um banco de dados: é o conteúdo, no mesmo padrão para
          exportar e importar.
        </p>
        <LinkDeArquivo className="botao botao-primario" href="/api/backup/exportar">
          Baixar backup completo
        </LinkDeArquivo>
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
      </>
      )}
      {aba === "propostas" && <MatrizesDeProposta />}
      {aba === "integracoes" && <IntegracoesDoSistema />}
      {aba === "grupos" && (
        <>
          <p className="campo-ajuda" style={{ margin: 0 }}>O cliente é o grupo. Junte os que a planilha separou.</p>
          <Grupos listas={listas} />
        </>
      )}
      {aba === "conferencia" && (
        <>
          <p className="campo-ajuda" style={{ margin: 0 }}>O que entrou da planilha, o que ficou pendente e o que foi ajustado.</p>
          <Conferencia listas={listas} />
        </>
      )}
      {aba === "servicos" && <PedidosDeServicoNovo />}
    </div>
  );
}

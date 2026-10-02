/** O painel de uma pessoa: os dados dela e todas as empresas em que está, com a marca de
 * contato principal em cada uma. Pedido de Karine em 30/09/2026.
 */

import type { Listas, PessoaComOrigem } from "../api/tipos";
import { api } from "../api/cliente";
import { ExclusaoConfirmada } from "../componentes/ExclusaoConfirmada";
import { PainelLateral } from "../componentes/PainelLateral";
import { FormularioDePessoa } from "./DetalheDoContato";
import { SEM_PERMISSAO, usarAcesso } from "../entrada";
import { AlteracoesDoRegistro } from "../componentes/HistoricoDeAlteracoes";

export function DetalheDaPessoa({
  pessoa,
  listas,
  aoFechar,
  aoMudar,
}: {
  pessoa: PessoaComOrigem;
  listas: Listas | null;
  aoFechar: () => void;
  aoMudar: () => void;
}) {
  const { pode } = usarAcesso();
  const empresas = pessoa.empresas ?? [];
  const salvar = async (corpo: Record<string, unknown>) => {
    await api.editarContato(pessoa.id, corpo);
    aoMudar();
  };

  return (
    <PainelLateral
      titulo={pessoa.nome}
      subtitulo={empresas.length ? `${empresas.length} empresa${empresas.length === 1 ? "" : "s"}` : "Sem empresa"}
      aoFechar={aoFechar}
      rodape={<button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>}
    >
      <div className="formulario">
        <h3 style={{ fontSize: 14 }}>Empresas</h3>
        {empresas.length === 0 ? (
          <p className="campo-ajuda" style={{ margin: 0 }}>
            Ainda não está em nenhuma empresa. Vincule em “Nova empresa” ou no painel da empresa.
          </p>
        ) : (
          <ul className="contatos-lista" aria-label="Empresas da pessoa">
            {empresas.map((e) => (
              <li key={e.empresa_id} className="contato-item">
                <div>
                  <strong>{e.principal ? "★ " : ""}{e.razao_social}</strong>
                  {e.principal && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>Principal</span>}
                  {e.razao_social !== e.grupo_nome && <span className="numero-nota"> · {e.grupo_nome}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}

        <h3 style={{ fontSize: 14 }}>Dados da pessoa</h3>
        <FormularioDePessoa key={pessoa.id} inicial={pessoa} papeis={listas?.papeis_de_contato ?? []}
          rotulo="Salvar contato" aoSalvar={salvar} />
      </div>

      <ExclusaoConfirmada
        rotulo="Excluir contato"
        bloqueio={pode("contatos.excluir") ? null : SEM_PERMISSAO}
        aviso={empresas.length === 0
          ? `${pessoa.nome} sai da base de contatos.`
          : empresas.length === 1
            ? `${pessoa.nome} sai da base e da empresa ${empresas[0].razao_social}.`
            : `${pessoa.nome} sai da base e das ${empresas.length} empresas em que está (${empresas.map((e) => e.razao_social).join(", ")}).`}
        aoConfirmar={async () => {
          await api.excluirPessoa(pessoa.id);
          aoMudar();
          aoFechar();
        }}
      />
      <AlteracoesDoRegistro tabela="pessoa_contato" id={pessoa.id} />
    </PainelLateral>
  );
}

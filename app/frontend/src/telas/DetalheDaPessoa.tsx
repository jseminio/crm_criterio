/** O painel de uma pessoa: os dados dela e todas as empresas em que está, com a marca de
 * contato principal em cada uma. Pedido de Karine em 30/09/2026.
 */

import type { Listas, PessoaComOrigem } from "../api/tipos";
import { api } from "../api/cliente";
import { PainelLateral } from "../componentes/PainelLateral";
import { FormularioDePessoa } from "./DetalheDoContato";

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
            {pessoa.grupo_nome
              ? `Ligada ao grupo ${pessoa.grupo_nome} (aparece em todas as empresas dele).`
              : "Ainda não está em nenhuma empresa. Vincule em “Nova empresa” ou no painel da empresa."}
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
    </PainelLateral>
  );
}

/** Cadastro de pessoa de contato direto no menu Contatos.
 *
 * Desde 30/09/2026 (pedido de Karine) a empresa é **opcional**: a pessoa entra na base única de
 * contatos e pode ser vinculada depois, em "Nova empresa" ou no painel de qualquer empresa. Se a
 * empresa já existir, dá para escolhê-la aqui mesmo. O contato é ligado só a empresas, nunca ao
 * grupo (01/10/2026): escolhido um prospect ainda sem empresa, ela nasce com o nome do grupo.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { EntidadeDeContato, Listas } from "../api/tipos";
import { PainelLateral } from "../componentes/PainelLateral";
import { cnpj as formatarCnpj } from "../formato";
import { usarDados } from "../usarDados";
import { FormularioDePessoa } from "./DetalheDoContato";

export function NovaPessoa({ listas, aoFechar, aoCriar }: { listas: Listas | null; aoFechar: () => void; aoCriar: () => void }) {
  const [busca, definirBusca] = useState("");
  const [escolhida, definirEscolhida] = useState<EntidadeDeContato | null>(null);
  const termo = busca.trim();

  const resultados = usarDados<EntidadeDeContato[]>(async () => {
    if (termo.length < 2) return [];
    const [c, p] = await Promise.all([api.contatosPorEmpresa("cliente", termo, false), api.contatosPorEmpresa("prospect", termo, false)]);
    return [...c.itens, ...p.itens].slice(0, 12);
  }, [termo]);

  const criar = async (corpo: Record<string, unknown>) => {
    let empresaId = escolhida?.empresa_id ?? null;
    if (escolhida && empresaId === null) empresaId = (await api.criarEmpresaDoGrupo(escolhida.grupo_id)).id;
    await api.criarContato(empresaId !== null ? { ...corpo, empresa_id: empresaId } : corpo);
    aoCriar();
    aoFechar();
  };

  return (
    <PainelLateral titulo="Nova pessoa" subtitulo="A pessoa entra na base de contatos; a empresa pode vir depois." aoFechar={aoFechar}>
      <div style={{ display: "grid", gap: "var(--e3)" }}>
        <h3 style={{ fontSize: 14 }}>1. Empresa (opcional)</h3>
        {escolhida ? (
          <div className="recado" role="status">
            <strong>{escolhida.razao_social ?? escolhida.grupo_nome}</strong>
            {escolhida.razao_social && escolhida.razao_social !== escolhida.grupo_nome && <span className="numero-nota"> · {escolhida.grupo_nome}</span>}
            <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>{escolhida.tipo === "cliente" ? "Cliente" : "Prospect"}</span>
            <div style={{ marginTop: "var(--e2)" }}>
              <button type="button" className="botao botao-secundario" onClick={() => definirEscolhida(null)}>Trocar</button>
            </div>
          </div>
        ) : (
          <>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="np-busca">Empresa, CNPJ ou grupo</label>
              <input id="np-busca" className="entrada" value={busca} onChange={(e) => definirBusca(e.target.value)} placeholder="deixe em branco para cadastrar sem empresa" />
            </div>
            {termo.length >= 2 && resultados.dados && resultados.dados.length === 0 && !resultados.carregando && (
              <p className="campo-ajuda" style={{ margin: 0 }}>Nada encontrado. Cadastre a pessoa sem empresa e vincule depois, em “Nova empresa”.</p>
            )}
            <ul className="contatos-lista" aria-label="Resultados da busca">
              {(resultados.dados ?? []).map((e) => (
                <li key={`${e.grupo_id}-${e.empresa_id ?? "g"}`} className="contato-item">
                  <div>
                    <strong>{e.razao_social ?? e.grupo_nome}</strong>
                    {e.razao_social && e.razao_social !== e.grupo_nome && <span className="numero-nota"> · {e.grupo_nome}</span>}
                    <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>{e.tipo === "cliente" ? "Cliente" : "Prospect"}</span>
                    {e.cnpj && <span className="numero-nota"> · {formatarCnpj(e.cnpj)}</span>}
                  </div>
                  <button type="button" className="botao botao-secundario" onClick={() => definirEscolhida(e)}>Escolher</button>
                </li>
              ))}
            </ul>
          </>
        )}

        {escolhida && escolhida.empresa_id === null && (
          <p className="campo-ajuda" style={{ margin: 0 }}>
            Este prospect ainda não tem empresa: ela será criada com o nome do grupo, e a pessoa vinculada a ela.
          </p>
        )}
        <h3 style={{ fontSize: 14 }}>2. Dados da pessoa</h3>
        <FormularioDePessoa papeis={listas?.papeis_de_contato ?? []} rotulo="Cadastrar pessoa" aoSalvar={criar} aoCancelar={aoFechar} />
      </div>
    </PainelLateral>
  );
}

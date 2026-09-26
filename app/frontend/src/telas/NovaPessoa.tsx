/** Cadastro de pessoa de contato direto no menu Contatos.
 *
 * A pessoa se liga a uma empresa **ou** ao grupo (a API exige uma das duas). Aqui a pessoa escolhe onde ela
 * trabalha buscando a empresa ou o grupo, entre clientes e prospects, e depois preenche os dados.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { EntidadeDeContato, Listas } from "../api/tipos";
import { PainelLateral } from "../componentes/PainelLateral";
import { cnpj as formatarCnpj } from "../formato";
import { usarDados } from "../usarDados";
import { FormularioDePessoa } from "./DetalheDoContato";

type Vinculo = "empresa" | "grupo";

export function NovaPessoa({ listas, aoFechar, aoCriar }: { listas: Listas | null; aoFechar: () => void; aoCriar: () => void }) {
  const [busca, definirBusca] = useState("");
  const [escolhida, definirEscolhida] = useState<EntidadeDeContato | null>(null);
  const [vinculo, definirVinculo] = useState<Vinculo>("empresa");
  const termo = busca.trim();

  const resultados = usarDados<EntidadeDeContato[]>(async () => {
    if (termo.length < 2) return [];
    const [c, p] = await Promise.all([api.contatosPorEmpresa("cliente", termo, false), api.contatosPorEmpresa("prospect", termo, false)]);
    return [...c.itens, ...p.itens].slice(0, 12);
  }, [termo]);

  const criar = async (corpo: Record<string, unknown>) => {
    if (!escolhida) return;
    const alvo = escolhida.empresa_id !== null && vinculo === "empresa" ? { empresa_id: escolhida.empresa_id } : { grupo_id: escolhida.grupo_id };
    await api.criarContato({ ...corpo, ...alvo });
    aoCriar();
    aoFechar();
  };

  return (
    <PainelLateral titulo="Nova pessoa" subtitulo="Cadastre quem falar em uma empresa ou grupo." aoFechar={aoFechar}>
      <div style={{ display: "grid", gap: "var(--e3)" }}>
        <h3 style={{ fontSize: 14 }}>1. Onde esta pessoa trabalha?</h3>
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
              <input id="np-busca" className="entrada" value={busca} onChange={(e) => definirBusca(e.target.value)} placeholder="digite ao menos 2 letras" autoFocus />
            </div>
            {termo.length >= 2 && resultados.dados && resultados.dados.length === 0 && !resultados.carregando && (
              <p className="campo-ajuda" style={{ margin: 0 }}>Nada encontrado. Cadastre a empresa ou o prospect antes.</p>
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
                  <button type="button" className="botao botao-secundario" onClick={() => { definirEscolhida(e); definirVinculo("empresa"); }}>Escolher</button>
                </li>
              ))}
            </ul>
          </>
        )}

        {escolhida && (
          <>
            {escolhida.empresa_id !== null && (
              <fieldset style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: "var(--e1)" }}>
                <legend className="campo-rotulo">A pessoa fica ligada a</legend>
                <label style={{ fontSize: 13 }}>
                  <input type="radio" name="np-vinculo" checked={vinculo === "empresa"} onChange={() => definirVinculo("empresa")} /> Só a esta empresa
                </label>
                <label style={{ fontSize: 13 }}>
                  <input type="radio" name="np-vinculo" checked={vinculo === "grupo"} onChange={() => definirVinculo("grupo")} /> Ao grupo todo (aparece em todas as empresas dele)
                </label>
              </fieldset>
            )}
            <h3 style={{ fontSize: 14 }}>2. Dados da pessoa</h3>
            <FormularioDePessoa papeis={listas?.papeis_de_contato ?? []} rotulo="Cadastrar pessoa" aoSalvar={criar} aoCancelar={aoFechar} />
          </>
        )}
      </div>
    </PainelLateral>
  );
}

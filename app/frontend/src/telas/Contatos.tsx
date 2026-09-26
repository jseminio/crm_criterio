/** Contatos: quem falar em cada empresa, de clientes e de prospects **separados**.
 *
 * Busca por **empresa** (razão social, CNPJ, nome do grupo) ou por **pessoa** (nome, cargo, e-mail,
 * telefone), sem depender de acento nem de caixa. Cliente = empresa (CNPJ); prospect = grupo, ou
 * a empresa quando já existe. A coluna de lacunas diz o que falta para poder falar com a pessoa
 * e mandar correspondência.
 */

import { useEffect, useState } from "react";
import { api } from "../api/cliente";
import type { EntidadeDeContato, Listas, PaginaDeContatos, PessoaComOrigem, TipoDeContato } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { cnpj as formatarCnpj, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDoContato } from "./DetalheDoContato";

type Modo = "empresa" | "pessoa";
const ROTULO: Record<TipoDeContato, string> = { cliente: "Clientes", prospect: "Prospects" };

/** Espera a pessoa parar de digitar antes de consultar. */
function useAtrasado(valor: string, ms = 250) {
  const [atrasado, definir] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => definir(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return atrasado;
}

function Lacunas({ itens }: { itens: string[] }) {
  if (itens.length === 0) return <span className="etiqueta etiqueta-ganho">Completo</span>;
  return (
    <span className="etiqueta etiqueta-espera" title={itens.join(", ")}>
      {itens.length} lacuna{itens.length === 1 ? "" : "s"}
    </span>
  );
}

export function Contatos({ listas }: { listas: Listas | null }) {
  const [tipo, definirTipo] = useState<TipoDeContato>("cliente");
  const [modo, definirModo] = useState<Modo>("empresa");
  const [texto, definirTexto] = useState("");
  const [soComLacunas, definirSoComLacunas] = useState(false);
  const [aberto, definirAberto] = useState<EntidadeDeContato | null>(null);
  const busca = useAtrasado(texto);

  const empresas = usarDados<PaginaDeContatos<EntidadeDeContato> | null>(
    () => (modo === "empresa" ? api.contatosPorEmpresa(tipo, busca, soComLacunas) : Promise.resolve(null)),
    [modo, tipo, busca, soComLacunas],
  );
  const pessoas = usarDados<PaginaDeContatos<PessoaComOrigem> | null>(
    () => (modo === "pessoa" ? api.contatosPorPessoa(tipo, busca) : Promise.resolve(null)),
    [modo, tipo, busca],
  );
  const atual = modo === "empresa" ? empresas : pessoas;
  const total = modo === "empresa" ? empresas.dados?.total : pessoas.dados?.total;

  const recarregar = () => { empresas.recarregar(); pessoas.recarregar(); };
  // O painel mostra a versão mais nova da entidade que está aberta.
  const aberta = aberto
    ? (empresas.dados?.itens.find((e) => e.grupo_id === aberto.grupo_id && e.empresa_id === aberto.empresa_id) ?? aberto)
    : null;

  const nada = !atual.carregando && !atual.erro && total === 0;
  return (
    <>
      <div className="abas" role="tablist" aria-label="Clientes e prospects">
        {(["cliente", "prospect"] as TipoDeContato[]).map((t) => (
          <button key={t} type="button" role="tab" className="aba" aria-selected={tipo === t}
            onClick={() => { definirTipo(t); definirAberto(null); }}>
            {ROTULO[t]}
          </button>
        ))}
      </div>

      <div className="filtros">
        <div className="campo">
          <span className="campo-rotulo" id="modo-rotulo">Buscar por</span>
          <div role="group" aria-labelledby="modo-rotulo" className="abas" style={{ borderBottom: 0 }}>
            {(["empresa", "pessoa"] as Modo[]).map((m) => (
              <button key={m} type="button" className="botao botao-secundario" aria-pressed={modo === m} onClick={() => definirModo(m)}>
                {m === "empresa" ? "Empresa" : "Pessoa"}
              </button>
            ))}
          </div>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="c-busca">
            {modo === "empresa" ? "Razão social, CNPJ ou grupo" : "Nome, cargo, e-mail ou telefone"}
          </label>
          <input id="c-busca" className="entrada entrada-busca" value={texto} onChange={(e) => definirTexto(e.target.value)}
            placeholder={modo === "empresa" ? "ex.: alfa, 11.222.333" : "ex.: maria, 99999"} />
        </div>
        {modo === "empresa" && (
          <label className="campo" style={{ alignSelf: "flex-end" }}>
            <span style={{ display: "flex", gap: "var(--e1)", alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={soComLacunas} onChange={(e) => definirSoComLacunas(e.target.checked)} />
              Só com lacunas
            </span>
          </label>
        )}
      </div>

      {atual.carregando && !atual.dados && <Carregando rotulo="Carregando os contatos" />}
      {atual.erro && !atual.carregando && <Erro mensagem={atual.erro} aoTentarDeNovo={recarregar} />}
      {nada && (texto || soComLacunas) && <VazioPorFiltro aoLimpar={() => { definirTexto(""); definirSoComLacunas(false); }} />}
      {nada && !texto && !soComLacunas && (
        <VazioSemDados
          titulo={modo === "empresa" ? `Nenhum ${tipo === "cliente" ? "cliente" : "prospect"} cadastrado` : "Nenhuma pessoa de contato ainda"}
          explicacao={modo === "pessoa" ? "Abra uma empresa na aba “Empresa” e adicione o primeiro contato." : "Os clientes vêm da carteira; os prospects, das propostas."}
        />
      )}

      {modo === "empresa" && !empresas.erro && (empresas.dados?.total ?? 0) > 0 && (
        <table className="tabela" aria-label="Empresas">
          <thead>
            <tr>
              <th scope="col">{tipo === "cliente" ? "Empresa" : "Prospect"}</th>
              <th scope="col">CNPJ</th>
              <th scope="col">Contatos</th>
              <th scope="col">Lacunas</th>
              <th scope="col" className="tabela-numero">{tipo === "cliente" ? "Mensalidade" : "Propostas"}</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {empresas.dados!.itens.map((e) => (
              <tr key={`${e.grupo_id}-${e.empresa_id ?? "g"}`}>
                <td>
                  <button type="button" className="link-de-tabela" onClick={() => definirAberto(e)}>{e.razao_social ?? e.grupo_nome}</button>
                  {e.razao_social && e.razao_social !== e.grupo_nome && <span className="numero-nota"> · {e.grupo_nome}</span>}
                </td>
                <td>{formatarCnpj(e.cnpj)}</td>
                <td>{e.contatos.length ? e.contatos.map((p) => p.nome).join(", ") : "—"}</td>
                <td><Lacunas itens={e.lacunas} /></td>
                <td className="tabela-numero">{tipo === "cliente" ? (e.mensalidade ? dinheiro(e.mensalidade) : "—") : e.propostas}</td>
                <td><button type="button" className="botao botao-secundario" onClick={() => definirAberto(e)}>Abrir</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modo === "pessoa" && !pessoas.erro && (pessoas.dados?.total ?? 0) > 0 && (
        <table className="tabela" aria-label="Pessoas">
          <thead>
            <tr>
              <th scope="col">Pessoa</th><th scope="col">Cargo</th><th scope="col">E-mail</th>
              <th scope="col">Telefone</th><th scope="col">{tipo === "cliente" ? "Empresa" : "Prospect"}</th>
            </tr>
          </thead>
          <tbody>
            {pessoas.dados!.itens.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.nome}</strong>
                  {p.nao_contatar && <span className="etiqueta etiqueta-perda" style={{ marginLeft: 6 }}>Não contatar</span>}
                </td>
                <td>{p.cargo ?? "—"}</td>
                <td>{p.email ?? "—"}</td>
                <td>{p.telefone ?? "—"}</td>
                <td>{p.razao_social ?? p.grupo_nome}{p.razao_social && p.razao_social !== p.grupo_nome && <span className="numero-nota"> · {p.grupo_nome}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {total !== undefined && total > 0 && <p className="numero-nota">{total} resultado{total === 1 ? "" : "s"}</p>}

      {aberta && <DetalheDoContato entidade={aberta} listas={listas} aoFechar={() => definirAberto(null)} aoMudar={recarregar} />}
    </>
  );
}

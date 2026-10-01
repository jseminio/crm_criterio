/** Contatos: quem falar em cada empresa, de clientes e de prospects **separados**.
 *
 * Busca por **empresa** (razão social, CNPJ, nome do grupo) ou por **pessoa** (nome, cargo, e-mail,
 * telefone), sem depender de acento nem de caixa. Cliente = empresa (CNPJ); prospect = grupo, ou
 * a empresa quando já existe. A coluna de lacunas diz o que falta para poder falar com a pessoa
 * e mandar correspondência.
 *
 * Base única de contatos (30/09/2026, pedido de Karine): "Nova pessoa" cadastra sem empresa, e
 * "Nova empresa" vincula quem já está cadastrado. Uma pessoa pode estar em várias empresas.
 */

import { useEffect, useState } from "react";
import { api } from "../api/cliente";
import type { EntidadeDeContato, Listas, PaginaDeContatos, PessoaComOrigem, TipoDeContato } from "../api/tipos";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { cnpj as formatarCnpj, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaPessoa } from "./DetalheDaPessoa";
import { DetalheDoContato } from "./DetalheDoContato";
import { NovaEmpresa } from "./NovaEmpresa";
import { NovaPessoa } from "./NovaPessoa";

/** As empresas da pessoa, com ★ onde é principal; sem nenhuma, "Sem empresa". */
function empresasDaPessoa(p: PessoaComOrigem): string {
  if (p.empresas && p.empresas.length > 0) {
    return p.empresas.map((e) => `${e.principal ? "★ " : ""}${e.razao_social}`).join(", ");
  }
  return "Sem empresa";
}

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
  const [cadastrando, definirCadastrando] = useState(false);
  const [cadastrandoEmpresa, definirCadastrandoEmpresa] = useState(false);
  const [pessoaAberta, definirPessoaAberta] = useState<PessoaComOrigem | null>(null);
  const { ordenacao: ordenacaoDeEmpresas, alternar: alternarOrdenacaoDeEmpresas } = usarOrdenacao();
  const { ordenacao: ordenacaoDePessoas, alternar: alternarOrdenacaoDePessoas } = usarOrdenacao();
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
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "var(--e2)" }}>
        <div className="sugestao-acoes">
          <button type="button" className="botao botao-primario" onClick={() => definirCadastrando(true)}>Nova pessoa</button>
          <button type="button" className="botao botao-primario" onClick={() => definirCadastrandoEmpresa(true)}>Nova empresa</button>
        </div>
      </div>

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
          explicacao={modo === "pessoa" ? "Use “Nova pessoa” para cadastrar o primeiro contato." : "Os clientes vêm da carteira; os prospects, das propostas."}
        />
      )}

      {modo === "empresa" && !empresas.erro && (empresas.dados?.total ?? 0) > 0 && (
        <table className="tabela" aria-label="Empresas">
          <thead>
            <tr>
              <ThOrdenavel coluna="nome" ordenacao={ordenacaoDeEmpresas} aoAlternar={alternarOrdenacaoDeEmpresas}>
                {tipo === "cliente" ? "Cliente" : "Prospect"}
              </ThOrdenavel>
              <ThOrdenavel coluna="cnpj" ordenacao={ordenacaoDeEmpresas} aoAlternar={alternarOrdenacaoDeEmpresas}>CNPJ</ThOrdenavel>
              <ThOrdenavel coluna="contatos" ordenacao={ordenacaoDeEmpresas} aoAlternar={alternarOrdenacaoDeEmpresas}>Contatos</ThOrdenavel>
              <ThOrdenavel coluna="lacunas" ordenacao={ordenacaoDeEmpresas} aoAlternar={alternarOrdenacaoDeEmpresas}>Lacunas</ThOrdenavel>
              <ThOrdenavel coluna="valor" numerico ordenacao={ordenacaoDeEmpresas} aoAlternar={alternarOrdenacaoDeEmpresas}>
                {tipo === "cliente" ? "Mensalidade" : "Propostas"}
              </ThOrdenavel>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {ordenar(empresas.dados!.itens, ordenacaoDeEmpresas, {
              nome: (e) => e.razao_social ?? e.grupo_nome,
              cnpj: (e) => e.cnpj,
              contatos: (e) => e.contatos.length,
              lacunas: (e) => e.lacunas.length,
              valor: (e) => (tipo === "cliente" ? (e.mensalidade ? Number(e.mensalidade) : null) : e.propostas),
            }).map((e) => (
              <tr key={`${e.grupo_id}-${e.empresa_id ?? "g"}`}>
                <td>
                  <button type="button" className="link-de-tabela" onClick={() => definirAberto(e)}>{e.razao_social ?? e.grupo_nome}</button>
                  {e.razao_social && e.razao_social !== e.grupo_nome && <span className="numero-nota"> · {e.grupo_nome}</span>}
                  {tipo === "cliente" && !e.recorrente && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>Não recorrente</span>}
                </td>
                <td>{formatarCnpj(e.cnpj)}</td>
                <td>{e.contatos.length ? e.contatos.map((p) => p.nome).join(", ") : "—"}</td>
                <td><Lacunas itens={e.lacunas} /></td>
                <td className="tabela-numero">{tipo === "cliente" ? (e.mensalidade ? dinheiro(e.mensalidade) : `${e.propostas} prop.`) : e.propostas}</td>
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
              <ThOrdenavel coluna="nome" ordenacao={ordenacaoDePessoas} aoAlternar={alternarOrdenacaoDePessoas}>Pessoa</ThOrdenavel>
              <ThOrdenavel coluna="cargo" ordenacao={ordenacaoDePessoas} aoAlternar={alternarOrdenacaoDePessoas}>Cargo</ThOrdenavel>
              <ThOrdenavel coluna="email" ordenacao={ordenacaoDePessoas} aoAlternar={alternarOrdenacaoDePessoas}>E-mail</ThOrdenavel>
              <ThOrdenavel coluna="telefone" ordenacao={ordenacaoDePessoas} aoAlternar={alternarOrdenacaoDePessoas}>Telefone</ThOrdenavel>
              <ThOrdenavel coluna="empresa" ordenacao={ordenacaoDePessoas} aoAlternar={alternarOrdenacaoDePessoas}>
                {tipo === "cliente" ? "Empresa" : "Prospect"}
              </ThOrdenavel>
            </tr>
          </thead>
          <tbody>
            {ordenar(pessoas.dados!.itens, ordenacaoDePessoas, {
              nome: (p) => p.nome,
              cargo: (p) => p.cargo,
              email: (p) => p.email,
              telefone: (p) => p.telefone,
              empresa: (p) => empresasDaPessoa(p),
            }).map((p) => (
              <tr key={p.id}>
                <td>
                  <button type="button" className="link-de-tabela" onClick={() => definirPessoaAberta(p)}><strong>{p.nome}</strong></button>
                  {p.nao_contatar && <span className="etiqueta etiqueta-perda" style={{ marginLeft: 6 }}>Não contatar</span>}
                </td>
                <td>{p.cargo ?? "—"}</td>
                <td>{p.email ?? "—"}</td>
                <td>{p.telefone ?? "—"}</td>
                <td>{p.empresas && p.empresas.length > 0 ? empresasDaPessoa(p) : <span className="numero-nota">— Sem empresa</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {total !== undefined && total > 0 && <p className="numero-nota">{total} resultado{total === 1 ? "" : "s"}</p>}

      {cadastrando && <NovaPessoa listas={listas} aoFechar={() => definirCadastrando(false)} aoCriar={recarregar} />}

      {cadastrandoEmpresa && <NovaEmpresa aoFechar={() => definirCadastrandoEmpresa(false)} aoCriar={recarregar} />}

      {pessoaAberta && (
        <DetalheDaPessoa
          pessoa={pessoas.dados?.itens.find((p) => p.id === pessoaAberta.id) ?? pessoaAberta}
          listas={listas}
          aoFechar={() => definirPessoaAberta(null)}
          aoMudar={recarregar}
        />
      )}

      {aberta && <DetalheDoContato entidade={aberta} listas={listas} aoFechar={() => definirAberto(null)} aoMudar={recarregar} />}
    </>
  );
}

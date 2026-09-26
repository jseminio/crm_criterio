/** O painel de uma empresa (cliente) ou de um grupo (prospect): contatos e endereço.
 *
 * Contato pode ser da empresa ou só do grupo. Prospect ainda não tem empresa, então o
 * endereço só aparece depois de "Cadastrar empresa" — é na empresa que ele mora.
 * **Não contatar** é gravado e respeitado pelas listas de campanha.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { EntidadeDeContato, Listas, PessoaDeContato } from "../api/tipos";
import { PainelLateral } from "../componentes/PainelLateral";
import { dinheiro } from "../formato";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

type Campos = Record<string, string>;
const vazio = (v: string | null | undefined) => v ?? "";

function FormularioDePessoa({
  inicial,
  papeis,
  rotulo,
  aoSalvar,
  aoCancelar,
}: {
  inicial?: PessoaDeContato;
  papeis: string[];
  rotulo: string;
  aoSalvar: (corpo: Record<string, unknown>) => Promise<void>;
  aoCancelar?: () => void;
}) {
  const [c, definirC] = useState<Campos>({
    nome: vazio(inicial?.nome), cargo: vazio(inicial?.cargo), email: vazio(inicial?.email),
    telefone: vazio(inicial?.telefone), papel: vazio(inicial?.papel), observacao: vazio(inicial?.observacao),
  });
  const [naoContatar, definirNaoContatar] = useState(inicial?.nao_contatar ?? false);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const mudar = (k: string, v: string) => definirC((a) => ({ ...a, [k]: v }));
  const id = inicial ? `p${inicial.id}` : "nova";

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo: Record<string, unknown> = Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]));
      corpo.nao_contatar = naoContatar;
      await aoSalvar(corpo);
      if (!inicial) {
        definirC({ nome: "", cargo: "", email: "", telefone: "", papel: "", observacao: "" });
        definirNaoContatar(false);
      }
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <div className="contato-form">
      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-nome`}>Nome</label>
          <input id={`${id}-nome`} className="entrada" maxLength={200} value={c.nome} onChange={(e) => mudar("nome", e.target.value)} />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-cargo`}>Cargo</label>
          <input id={`${id}-cargo`} className="entrada" maxLength={100} value={c.cargo} onChange={(e) => mudar("cargo", e.target.value)} />
        </div>
      </div>
      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-email`}>E-mail</label>
          <input id={`${id}-email`} type="email" className="entrada" maxLength={200} value={c.email} onChange={(e) => mudar("email", e.target.value)} />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-tel`}>Telefone</label>
          <input id={`${id}-tel`} className="entrada" maxLength={30} value={c.telefone} onChange={(e) => mudar("telefone", e.target.value)} />
        </div>
      </div>
      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-papel`}>Papel</label>
          <select id={`${id}-papel`} className="selecao" value={c.papel} onChange={(e) => mudar("papel", e.target.value)}>
            <option value="">Não informado</option>
            {papeis.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={`${id}-obs`}>Observação</label>
          <input id={`${id}-obs`} className="entrada" value={c.observacao} onChange={(e) => mudar("observacao", e.target.value)} />
        </div>
      </div>
      <label style={{ display: "flex", gap: "var(--e1)", alignItems: "center", fontSize: 13 }}>
        <input type="checkbox" checked={naoContatar} onChange={(e) => definirNaoContatar(e.target.checked)} />
        Não contatar (pediu para não ser contatado)
      </label>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      <div className="sugestao-acoes">
        {aoCancelar && <button type="button" className="botao botao-secundario" onClick={aoCancelar}>Cancelar</button>}
        <button type="button" className="botao botao-primario" disabled={salvando || c.nome.trim() === ""} onClick={salvar}>
          {salvando ? "Salvando…" : rotulo}
        </button>
      </div>
    </div>
  );
}

function Endereco({ entidade, aoMudar }: { entidade: EntidadeDeContato; aoMudar: () => void }) {
  const e = entidade.endereco;
  const [c, definirC] = useState<Campos>({
    razao_social: vazio(entidade.razao_social), cnpj: vazio(entidade.cnpj), logradouro: vazio(e.logradouro),
    numero: vazio(e.numero), complemento: vazio(e.complemento), bairro: vazio(e.bairro),
    municipio: vazio(e.municipio), uf: vazio(e.uf), cep: vazio(e.cep),
  });
  const [erro, definirErro] = useState<string | null>(null);
  const [ok, definirOk] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const mudar = (k: string, v: string) => { definirC((a) => ({ ...a, [k]: v })); definirOk(false); };

  const campo = (k: string, rotulo: string, largo = false) => (
    <div className="campo-bloco" style={largo ? { gridColumn: "1 / -1" } : undefined}>
      <label className="campo-rotulo" htmlFor={`end-${k}`}>{rotulo}</label>
      <input id={`end-${k}`} className="entrada" value={c[k]} onChange={(ev) => mudar(k, ev.target.value)} />
    </div>
  );

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo = Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]));
      await api.editarEmpresa(entidade.empresa_id!, corpo);
      definirOk(true);
      aoMudar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <div className="formulario">
      <h3 style={{ fontSize: 14 }}>Empresa e endereço</h3>
      <div className="formulario-duplo">{campo("razao_social", "Razão social")}{campo("cnpj", "CNPJ")}</div>
      <div className="formulario-duplo">{campo("logradouro", "Logradouro")}{campo("numero", "Número")}</div>
      <div className="formulario-duplo">{campo("complemento", "Complemento")}{campo("bairro", "Bairro")}</div>
      <div className="formulario-duplo">
        {campo("municipio", "Município")}
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="end-uf">UF</label>
          <select id="end-uf" className="selecao" value={c.uf} onChange={(ev) => mudar("uf", ev.target.value)}>
            <option value="">—</option>
            {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
      </div>
      <div className="formulario-duplo">{campo("cep", "CEP")}<span /></div>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      {ok && <p role="status" className="numero-nota">Salvo.</p>}
      <button type="button" className="botao botao-primario" disabled={salvando} onClick={salvar}>
        {salvando ? "Salvando…" : "Salvar empresa e endereço"}
      </button>
    </div>
  );
}

export function DetalheDoContato({
  entidade,
  listas,
  aoFechar,
  aoMudar,
}: {
  entidade: EntidadeDeContato;
  listas: Listas | null;
  aoFechar: () => void;
  aoMudar: () => void;
}) {
  const [editando, definirEditando] = useState<number | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const papeis = listas?.papeis_de_contato ?? [];
  const titulo = entidade.razao_social ?? entidade.grupo_nome;

  const criar = async (corpo: Record<string, unknown>) => {
    await api.criarContato(entidade.empresa_id ? { ...corpo, empresa_id: entidade.empresa_id } : { ...corpo, grupo_id: entidade.grupo_id });
    aoMudar();
  };
  const editar = (id: number) => async (corpo: Record<string, unknown>) => {
    await api.editarContato(id, corpo);
    definirEditando(null);
    aoMudar();
  };
  const cadastrarEmpresa = async () => {
    definirErro(null);
    try {
      await api.criarEmpresaDoGrupo(entidade.grupo_id);
      aoMudar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao cadastrar a empresa.");
    }
  };

  return (
    <PainelLateral
      titulo={titulo}
      subtitulo={
        entidade.tipo === "cliente"
          ? `${entidade.recorrente ? "Cliente" : "Cliente não recorrente"} · ${entidade.grupo_nome}${entidade.mensalidade ? ` · ${dinheiro(entidade.mensalidade)}/mês` : ""}`
          : `Prospect · ${entidade.propostas} proposta${entidade.propostas === 1 ? "" : "s"}`
      }
      aoFechar={aoFechar}
      rodape={<button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>}
    >
      {entidade.lacunas.length > 0 ? (
        <div className="recado" role="note">
          <strong>Falta:</strong> {entidade.lacunas.join(" · ")}
        </div>
      ) : (
        <div className="recado" role="note">Contato e endereço completos.</div>
      )}

      <div className="formulario">
        <h3 style={{ fontSize: 14 }}>Contatos ({entidade.contatos.length})</h3>
        {entidade.contatos.length === 0 && <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum contato cadastrado ainda.</p>}
        <ul className="contatos-lista">
          {entidade.contatos.map((p) =>
            editando === p.id ? (
              <li key={p.id}>
                <FormularioDePessoa inicial={p} papeis={papeis} rotulo="Salvar contato" aoSalvar={editar(p.id)} aoCancelar={() => definirEditando(null)} />
              </li>
            ) : (
              <li key={p.id} className="contato-item">
                <div>
                  <strong>{p.nome}</strong>
                  {p.cargo && <span className="numero-nota"> · {p.cargo}</span>}
                  {p.papel && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>{p.papel}</span>}
                  {p.do_grupo && <span className="numero-nota"> · do grupo</span>}
                  {p.nao_contatar && <span className="etiqueta etiqueta-perda" style={{ marginLeft: 6 }}>Não contatar</span>}
                </div>
                <div className="numero-nota">{[p.email, p.telefone].filter(Boolean).join(" · ") || "sem e-mail nem telefone"}</div>
                <button type="button" className="botao botao-secundario" onClick={() => definirEditando(p.id)}>Editar</button>
              </li>
            ),
          )}
        </ul>
        <h3 style={{ fontSize: 14 }}>Adicionar contato</h3>
        <FormularioDePessoa papeis={papeis} rotulo="Adicionar contato" aoSalvar={criar} />
      </div>

      {entidade.empresa_id !== null ? (
        <Endereco key={entidade.empresa_id} entidade={entidade} aoMudar={aoMudar} />
      ) : (
        <div className="recado">
          Este prospect ainda não tem empresa cadastrada, e é na empresa que o endereço mora.
          {erro && <p role="alert" className="estado-texto">{erro}</p>}
          <div style={{ marginTop: "var(--e2)" }}>
            <button type="button" className="botao botao-secundario" onClick={cadastrarEmpresa}>Cadastrar empresa</button>
          </div>
        </div>
      )}
    </PainelLateral>
  );
}

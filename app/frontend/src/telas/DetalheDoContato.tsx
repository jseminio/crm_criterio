/** O painel de uma empresa (cliente) ou de um grupo (prospect): contatos e endereço.
 *
 * Contato é ligado só a empresas, nunca ao grupo (01/10/2026). Prospect ainda sem empresa ganha
 * uma com "Cadastrar empresa" (ou ao adicionar o primeiro contato) — é nela que o endereço mora.
 * O grupo é informado na empresa.
 * **Não contatar** é gravado e respeitado pelas listas de campanha.
 *
 * Na empresa, o contato pode ser marcado como principal (pode haver vários), desvinculado, e uma
 * pessoa já cadastrada pode ser vinculada pela busca — pedido de Karine em 30/09/2026.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { EntidadeDeContato, Listas, PessoaDeContato } from "../api/tipos";
import { BuscaDeContato } from "../componentes/BuscaDeContato";
import { CampoDeGrupo } from "../componentes/CampoDeGrupo";
import { ExclusaoConfirmada } from "../componentes/ExclusaoConfirmada";
import { PainelLateral } from "../componentes/PainelLateral";
import { dinheiro } from "../formato";
import { SEM_PERMISSAO, usarAcesso } from "../entrada";
import { AlteracoesDoRegistro } from "../componentes/HistoricoDeAlteracoes";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

type Campos = Record<string, string>;
const vazio = (v: string | null | undefined) => v ?? "";

export function FormularioDePessoa({
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
    municipio: vazio(e.municipio), uf: vazio(e.uf), cep: vazio(e.cep), nome_do_grupo: entidade.grupo_nome,
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
      const corpo: Record<string, unknown> = Object.fromEntries(
        Object.entries(c).map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]),
      );
      // Grupo só vai quando mudou: empresa com contrato não troca de grupo.
      if ((corpo.nome_do_grupo ?? "") === entidade.grupo_nome || corpo.nome_do_grupo === null) delete corpo.nome_do_grupo;
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
      <CampoDeGrupo id="end-grupo" valor={c.nome_do_grupo} aoMudar={(v) => mudar("nome_do_grupo", v)}
        desabilitado={entidade.tem_contrato}
        ajuda={entidade.tem_contrato ? "Empresa com contrato não troca de grupo; use a fusão de grupos." : undefined} />
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
  const { pode } = usarAcesso();
  const [editando, definirEditando] = useState<number | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const papeis = listas?.papeis_de_contato ?? [];
  const titulo = entidade.razao_social ?? entidade.grupo_nome;

  const criar = async (corpo: Record<string, unknown>) => {
    // Contato é ligado só a empresas: prospect ainda sem empresa ganha uma com o nome do grupo.
    const empresaId = entidade.empresa_id ?? (await api.criarEmpresaDoGrupo(entidade.grupo_id)).id;
    await api.criarContato({ ...corpo, empresa_id: empresaId });
    aoMudar();
  };
  const editar = (id: number) => async (corpo: Record<string, unknown>) => {
    await api.editarContato(id, corpo);
    definirEditando(null);
    aoMudar();
  };
  const empresaId = entidade.empresa_id;
  const acao = (fazer: () => Promise<unknown>) => async () => {
    definirErro(null);
    try {
      await fazer();
      aoMudar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    }
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
                  <strong>{p.principal ? "★ " : ""}{p.nome}</strong>
                  {p.principal && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>Principal</span>}
                  {p.cargo && <span className="numero-nota"> · {p.cargo}</span>}
                  {p.papel && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>{p.papel}</span>}
                  {p.nao_contatar && <span className="etiqueta etiqueta-perda" style={{ marginLeft: 6 }}>Não contatar</span>}
                </div>
                <div className="numero-nota">{[p.email, p.telefone].filter(Boolean).join(" · ") || "sem e-mail nem telefone"}</div>
                <div className="sugestao-acoes" style={{ justifyContent: "flex-start" }}>
                  <button type="button" className="botao botao-secundario" onClick={() => definirEditando(p.id)}>Editar</button>
                  {empresaId !== null && (
                    <>
                      <label style={{ display: "flex", gap: "var(--e1)", alignItems: "center", fontSize: 13 }}>
                        <input type="checkbox" checked={p.principal ?? false}
                          onChange={(e) => void acao(() => api.marcarPrincipal(empresaId, p.id, e.target.checked))()} />
                        Contato principal
                      </label>
                      <button type="button" className="botao botao-secundario"
                        onClick={acao(() => api.desvincularContato(empresaId, p.id))}>
                        Desvincular
                      </button>
                    </>
                  )}
                </div>
              </li>
            ),
          )}
        </ul>
        {erro && empresaId !== null && <p role="alert" className="estado-texto">{erro}</p>}
        {empresaId !== null && (
          <>
            <h3 style={{ fontSize: 14 }}>Vincular contato já cadastrado</h3>
            <BuscaDeContato
              id="dc-busca-contato"
              jaVinculados={entidade.contatos.map((p) => p.id)}
              aoEscolher={(pessoa) => void acao(() => api.vincularContato(empresaId, pessoa.id))()}
            />
          </>
        )}
        <h3 style={{ fontSize: 14 }}>Adicionar contato</h3>
        <FormularioDePessoa papeis={papeis} rotulo="Adicionar contato" aoSalvar={criar} />
      </div>

      {entidade.empresa_id !== null ? (
        <>
          <Endereco key={entidade.empresa_id} entidade={entidade} aoMudar={aoMudar} />
          <ExclusaoConfirmada
            rotulo="Excluir empresa"
            bloqueio={entidade.tem_contrato ? "Esta empresa tem contrato e não pode ser excluída. Encerre ou mova o contrato antes." : pode("contatos.excluir") ? null : SEM_PERMISSAO}
            aviso={(() => {
              const vinculados = entidade.contatos.length;
              return vinculados
                ? `${vinculados} contato${vinculados === 1 ? "" : "s"} vinculado${vinculados === 1 ? "" : "s"} continua${vinculados === 1 ? "" : "m"} na base; só o vínculo com a empresa some. O grupo ${entidade.grupo_nome} fica.`
                : `O grupo ${entidade.grupo_nome} fica.`;
            })()}
            aoConfirmar={async () => {
              await api.excluirEmpresa(entidade.empresa_id!);
              aoMudar();
              aoFechar();
            }}
          />
          <AlteracoesDoRegistro tabela="empresa" id={entidade.empresa_id} />
        </>
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

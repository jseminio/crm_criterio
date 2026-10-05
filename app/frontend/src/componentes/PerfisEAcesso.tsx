/** Configurações › Perfis e acesso (E1, amostra aprovada por Eduardo em 02/10/2026).
 *
 * Os perfis liberam funcionalidades dentro de cada menu, ou o menu inteiro de uma vez. Aqui se
 * libera cada pessoa e se escolhe o perfil. O Administrador tem tudo e não se muda; precisa sobrar
 * pelo menos um ativo (o servidor confere).
 *
 * No login com e-mail e senha (issue #89), quem administra cadastra a pessoa com uma senha
 * provisória (o perfil já vem no Administrador) e pode redefinir a senha de qualquer uma. No modo
 * Microsoft (desligado, código guardado), a pessoa entra pela conta Microsoft e não há senha aqui.
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { MenuDoCatalogo, PerfilDeAcesso, UsuarioDoCrm } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { CampoDeSenha, problemaDaSenha } from "./CampoDeSenha";
import { Carregando, Erro } from "./estados";

export function PerfisEAcesso() {
  const comSenha = usarAcesso().eu.modo === "senha";
  const [senhaDoNovo, definirSenhaDoNovo] = useState("");
  const [redefinindo, definirRedefinindo] = useState<{ id: number; senha: string } | null>(null);
  const [catalogo, definirCatalogo] = useState<MenuDoCatalogo[] | null>(null);
  const [perfis, definirPerfis] = useState<PerfilDeAcesso[]>([]);
  const [usuarios, definirUsuarios] = useState<UsuarioDoCrm[]>([]);
  const [escolhido, definirEscolhido] = useState<number | null>(null);
  const [marcadas, definirMarcadas] = useState<Set<string>>(new Set());
  const [nomeNovo, definirNomeNovo] = useState("");
  const [emailNovo, definirEmailNovo] = useState("");
  const [perfilDoNovo, definirPerfilDoNovo] = useState<number | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [recado, definirRecado] = useState<string | null>(null);
  const [erroAoAbrir, definirErroAoAbrir] = useState<string | null>(null);

  const carregar = () => {
    definirErroAoAbrir(null);
    Promise.all([api.catalogoDeAcesso(), api.perfis(), api.usuarios()])
      .then(([c, p, u]) => {
        definirCatalogo(c);
        definirPerfis(p);
        definirUsuarios(u);
        const primeiro = p.find((x) => !x.administrador) ?? p[0];
        if (primeiro && escolhido === null) {
          definirEscolhido(primeiro.id);
          definirMarcadas(new Set(primeiro.permissoes));
        }
        // Modo senha: quem é cadastrado já vem como Administrador (decisão do dono, issue #89).
        if (perfilDoNovo === null) definirPerfilDoNovo((p.find((x) => (comSenha ? x.administrador : !x.administrador)) ?? p[0])?.id ?? null);
      })
      .catch((f) => definirErroAoAbrir(f instanceof ErroDaApi ? f.message : "Falha ao abrir os perfis."));
  };
  useEffect(carregar, []);

  if (erroAoAbrir) return <Erro mensagem={erroAoAbrir} aoTentarDeNovo={carregar} />;
  if (!catalogo) return <Carregando rotulo="Abrindo perfis e acesso" />;

  const perfil = perfis.find((p) => p.id === escolhido) ?? null;
  const tentar = async (acao: () => Promise<unknown>, ok: string) => {
    definirErro(null);
    definirRecado(null);
    try {
      await acao();
      definirRecado(ok);
      return true;
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
      return false;
    }
  };
  const recarregarListas = async () => {
    const [p, u] = await Promise.all([api.perfis(), api.usuarios()]);
    definirPerfis(p);
    definirUsuarios(u);
  };
  const escolher = (p: PerfilDeAcesso) => {
    definirEscolhido(p.id);
    definirMarcadas(new Set(p.permissoes));
    definirErro(null);
    definirRecado(null);
  };
  const alternar = (chaves: string[], ligar: boolean) => {
    const nova = new Set(marcadas);
    chaves.forEach((c) => (ligar ? nova.add(c) : nova.delete(c)));
    definirMarcadas(nova);
  };
  const mudou = perfil && !perfil.administrador && JSON.stringify([...marcadas].sort()) !== JSON.stringify([...perfil.permissoes].sort());

  return (
    <section className="numero perfis" aria-labelledby="perfis-titulo">
      <h3 className="numero-rotulo" id="perfis-titulo">Perfis e acesso</h3>
      <p className="campo-ajuda">
        Marque o menu inteiro ou só as funcionalidades dentro dele. Quem não tem nenhuma funcionalidade de um menu não vê o menu.
      </p>

      <div className="perfis-lista" role="tablist" aria-label="Perfis">
        {perfis.map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={p.id === escolhido} className="perfis-chip" onClick={() => escolher(p)}>
            {p.id === escolhido ? "✓ " : ""}{p.nome} <span className="campo-ajuda">· {p.pessoas} pessoa{p.pessoas === 1 ? "" : "s"}</span>
          </button>
        ))}
      </div>
      <div className="perfis-novo">
        <input className="entrada" value={nomeNovo} maxLength={60} placeholder="Nome do perfil novo (ex.: Customer Success)"
          aria-label="Nome do perfil novo" onChange={(e) => definirNomeNovo(e.target.value)} />
        <button type="button" className="botao botao-secundario" disabled={!nomeNovo.trim()}
          onClick={async () => {
            let criado: PerfilDeAcesso | null = null;
            if (await tentar(async () => { criado = await api.criarPerfil(nomeNovo.trim(), []); }, `Perfil ${nomeNovo.trim()} criado: marque o que ele libera.`)) {
              definirNomeNovo("");
              await recarregarListas();
              if (criado) escolher(criado);
            }
          }}>
          + Criar perfil
        </button>
      </div>

      {perfil && (
        perfil.administrador ? (
          <p className="recado">O <strong>{perfil.nome}</strong> tem tudo, inclusive o que for criado depois, e não se muda.</p>
        ) : (
          <>
            <div className="tabela-rolagem">
              <table className="tabela perfis-tabela" aria-label={`Permissões do perfil ${perfil.nome}`}>
                <thead>
                  <tr><th scope="col">Menu</th><th scope="col">Menu inteiro</th><th scope="col">Funcionalidades dentro do menu</th></tr>
                </thead>
                <tbody>
                  {catalogo.map((m) => {
                    const chaves = m.funcionalidades.map((f) => f.chave);
                    const todas = chaves.every((c) => marcadas.has(c));
                    return (
                      <tr key={m.chave}>
                        <th scope="row">{m.rotulo}</th>
                        <td>
                          <input type="checkbox" checked={todas} aria-label={`${m.rotulo}: menu inteiro`}
                            onChange={(e) => alternar(chaves, e.target.checked)} />
                        </td>
                        <td>
                          <div className="perfis-funcoes">
                            {m.funcionalidades.map((f) => (
                              <label key={f.chave}>
                                <input type="checkbox" checked={marcadas.has(f.chave)} onChange={(e) => alternar([f.chave], e.target.checked)} />
                                {f.rotulo}
                              </label>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="perfis-acoes">
              <button type="button" className="botao botao-primario" disabled={!mudou}
                onClick={async () => {
                  if (await tentar(() => api.mudarPerfil(perfil.id, { permissoes: [...marcadas] }), `Perfil ${perfil.nome} salvo. Vale na próxima ação de quem tem esse perfil.`)) {
                    await recarregarListas();
                  }
                }}>
                Salvar o perfil {perfil.nome}
              </button>
              {mudou && <span className="campo-ajuda">· alterações ainda não salvas</span>}
            </div>
          </>
        )
      )}

      {erro && <p className="estado estado-erro estado-texto" role="alert">✗ {erro}</p>}
      {recado && <p className="recado" role="status">✓ {recado}</p>}

      <h4 className="perfis-subtitulo">Pessoas com acesso</h4>
      <div className="tabela-rolagem">
        <table className="tabela" aria-label="Pessoas com acesso">
          <thead>
            <tr><th scope="col">{comSenha ? "E-mail" : "Conta Microsoft"}</th><th scope="col">Perfil</th><th scope="col">Situação</th><th scope="col">Desde</th></tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td>
                  {u.email}
                  {u.nome && <span className="celula-fonte">{u.nome}</span>}
                </td>
                <td>
                  <select className="selecao" value={u.perfil_id} aria-label={`Perfil de ${u.email}`}
                    onChange={(e) => void tentar(async () => { await api.mudarUsuario(u.id, { perfil_id: Number(e.target.value) }); await recarregarListas(); },
                      `${u.email} agora tem outro perfil.`)}>
                    {perfis.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
                  </select>
                </td>
                <td>
                  <span className={`etiqueta etiqueta-${u.ativo ? "ganho" : "neutra"}`}>{u.ativo ? "✓ ativo" : "sem acesso"}</span>{" "}
                  <button type="button" className="link-de-tabela"
                    onClick={() => void tentar(async () => { await api.mudarUsuario(u.id, { ativo: !u.ativo }); await recarregarListas(); },
                      u.ativo ? `${u.email} perdeu o acesso.` : `${u.email} voltou a ter acesso.`)}>
                    {u.ativo ? "tirar acesso" : "devolver acesso"}
                  </button>
                  {comSenha && redefinindo?.id !== u.id && (
                    <>
                      {" · "}
                      <button type="button" className="link-de-tabela" aria-label={`Redefinir senha de ${u.email}`}
                        onClick={() => { definirErro(null); definirRecado(null); definirRedefinindo({ id: u.id, senha: "" }); }}>
                        redefinir senha
                      </button>
                    </>
                  )}
                  {comSenha && redefinindo?.id === u.id && (
                    <form className="redefinir-senha" noValidate aria-label={`Redefinir a senha de ${u.email}`}
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const problema = problemaDaSenha(redefinindo.senha);
                        if (problema) {
                          definirRecado(null);
                          definirErro(problema);
                          return;
                        }
                        if (await tentar(() => api.redefinirSenha(u.id, redefinindo.senha),
                          `Senha de ${u.email} redefinida. Passe a senha nova para a pessoa; ela pode trocá-la depois em “Trocar senha”.`)) {
                          definirRedefinindo(null);
                        }
                      }}>
                      <CampoDeSenha valor={redefinindo.senha} aoMudar={(senha) => definirRedefinindo({ id: u.id, senha })}
                        autoComplete="new-password" rotuloAcessivel={`Nova senha provisória de ${u.email}`} dica="Nova senha provisória" exigido />
                      <button type="submit" className="botao botao-secundario">Salvar senha</button>
                      <button type="button" className="link-de-tabela" onClick={() => definirRedefinindo(null)}>cancelar</button>
                    </form>
                  )}
                </td>
                <td>{data(u.criado_em)}{u.liberado_por && <span className="celula-fonte">por {u.liberado_por}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="perfis-novo">
        <input className="entrada" value={emailNovo} placeholder="conta@grupocriterio.com.br"
          type={comSenha ? "email" : "text"} aria-label={comSenha ? "E-mail da pessoa" : "Conta Microsoft da pessoa"}
          onChange={(e) => definirEmailNovo(e.target.value)} />
        {comSenha && (
          <CampoDeSenha valor={senhaDoNovo} aoMudar={definirSenhaDoNovo} autoComplete="new-password"
            rotuloAcessivel="Senha provisória" dica="Senha provisória (mín. 8)" exigido />
        )}
        <select className="selecao" value={perfilDoNovo ?? ""} aria-label="Perfil da pessoa"
          onChange={(e) => definirPerfilDoNovo(Number(e.target.value))}>
          {perfis.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
        </select>
        <button type="button" className="botao botao-secundario"
          disabled={!emailNovo.trim() || perfilDoNovo === null || (comSenha && !senhaDoNovo)}
          onClick={async () => {
            const email = emailNovo.trim();
            if (comSenha) {
              const problema = problemaDaSenha(senhaDoNovo);
              if (problema) {
                definirRecado(null);
                definirErro(`Senha provisória: ${problema}`);
                return;
              }
            }
            const liberou = comSenha
              ? await tentar(() => api.liberarUsuario(email, perfilDoNovo!, senhaDoNovo),
                `${email} pode entrar. Passe a senha provisória para a pessoa; ela pode trocá-la depois em “Trocar senha”.`)
              : await tentar(() => api.liberarUsuario(email, perfilDoNovo!), `${email} liberado. Na primeira entrada, o nome vem da Microsoft.`);
            if (liberou) {
              definirEmailNovo("");
              definirSenhaDoNovo("");
              await recarregarListas();
            }
          }}>
          {comSenha ? "Cadastrar pessoa" : "Liberar acesso"}
        </button>
      </div>
    </section>
  );
}

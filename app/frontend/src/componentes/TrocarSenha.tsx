/** A pessoa logada troca a própria senha (issue #89). Não é obrigatório: quem recebeu uma senha
 * provisória troca quando quiser, pelo "Trocar senha" ao lado do nome. */

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ErroDaApi, guardarSessao } from "../api/cliente";
import { CampoDeSenha, problemaDaSenha } from "./CampoDeSenha";
import { PainelLateral } from "./PainelLateral";

export function TrocarSenha({ aoFechar }: { aoFechar: () => void }) {
  const [atual, definirAtual] = useState("");
  const [nova, definirNova] = useState("");
  const [repetida, definirRepetida] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [enviando, definirEnviando] = useState(false);
  const [trocada, definirTrocada] = useState(false);
  const primeiro = useRef<HTMLInputElement>(null);

  useEffect(() => {
    primeiro.current?.focus();
  }, []);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (enviando) return;
    const problema = !atual
      ? "Digite a senha atual."
      : problemaDaSenha(nova) ?? (nova !== repetida ? "A senha nova e a repetição não são iguais." : null);
    if (problema) {
      definirErro(problema);
      return;
    }
    definirErro(null);
    definirEnviando(true);
    try {
      // O servidor invalida os tokens antigos e devolve uma sessão nova: guardá-la mantém a pessoa logada.
      const sessao = await api.trocarMinhaSenha(atual, nova);
      if (sessao?.token) guardarSessao({ token: sessao.token, expira_em: sessao.expira_em });
      definirTrocada(true);
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Não consegui trocar a senha.");
    } finally {
      definirEnviando(false);
    }
  };

  return (
    <PainelLateral titulo="Trocar senha" subtitulo="Você continua conectado; a senha nova vale nas próximas entradas." aoFechar={aoFechar}>
      {trocada ? (
        <div className="trocar-senha">
          <p className="recado" role="status">✓ Senha trocada. Você continua conectado; use a senha nova na próxima vez que entrar.</p>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>
        </div>
      ) : (
        <form className="trocar-senha" onSubmit={enviar} noValidate aria-label="Trocar a minha senha">
          <div className="campo">
            <label className="campo-rotulo" htmlFor="senha-atual">Senha atual</label>
            <CampoDeSenha id="senha-atual" campoRef={primeiro} valor={atual} aoMudar={definirAtual} autoComplete="current-password" exigido />
          </div>
          <div className="campo">
            <label className="campo-rotulo" htmlFor="senha-nova">Senha nova</label>
            <CampoDeSenha id="senha-nova" valor={nova} aoMudar={definirNova} autoComplete="new-password" descritoPor="senha-nova-ajuda" exigido />
            <p className="campo-ajuda" id="senha-nova-ajuda">Pelo menos 8 caracteres.</p>
          </div>
          <div className="campo">
            <label className="campo-rotulo" htmlFor="senha-repetida">Repita a senha nova</label>
            <CampoDeSenha id="senha-repetida" valor={repetida} aoMudar={definirRepetida} autoComplete="new-password" exigido />
          </div>
          {erro && <p className="estado estado-erro estado-texto" role="alert">✗ {erro}</p>}
          <div className="perfis-acoes">
            <button type="submit" className="botao botao-primario" disabled={enviando} aria-busy={enviando}>
              {enviando ? "Trocando…" : "Trocar senha"}
            </button>{" "}
            <button type="button" className="botao botao-secundario" onClick={aoFechar}>Cancelar</button>
          </div>
        </form>
      )}
    </PainelLateral>
  );
}

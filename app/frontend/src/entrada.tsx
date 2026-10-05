/** Entrada no CRM (E1, 02/10/2026; login com e-mail e senha na issue #89).
 *
 * A API diz como entrar (`/api/acesso/entrada`):
 * - `senha`: a pessoa entra com e-mail e senha (`POST /api/acesso/login`). O token fica no
 *   `sessionStorage` e vai em cada pedido; vencido (`expira_em`) ou recusado (401), volta para cá.
 * - `microsoft` (desligado em 10/2026, código guardado): entra pelo Microsoft Entra (MSAL, com
 *   redirecionamento) e cada pedido leva o token da Microsoft.
 * - sem configuração: o CRM segue sem login, como antes do E1, e a tela avisa.
 * Em todos, o CRM decide o que a pessoa pode (`/api/eu`, com as permissões do perfil).
 */

import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  api,
  apagarSessao,
  definirEntrada,
  ErroDaApi,
  guardarSessao,
  lerSessao,
  sessaoAtual,
  sessaoVencida,
  type SessaoGuardada,
} from "./api/cliente";
import type { ConfiguracaoDeEntrada, Eu } from "./api/tipos";
import { CampoDeSenha } from "./componentes/CampoDeSenha";

export const SESSAO_EXPIROU = "Sua sessão expirou. Entre de novo.";

interface Acesso {
  eu: Eu;
  /** Basta uma das permissões; o Administrador e o modo sem login podem tudo. */
  pode: (...permissoes: string[]) => boolean;
  sair: () => void;
}

/** O porquê de um botão travado pelo perfil: estado nunca só por cor (PAD-002). */
export const SEM_PERMISSAO = "O seu perfil não libera esta ação. Peça a quem administra em Configurações › Perfis e acesso.";

const SEM_LOGIN: Eu = { modo: "local", email: null, nome: null, perfil: "Sem login", administrador: true, permissoes: [] };
const ContextoDeAcesso = createContext<Acesso>({ eu: SEM_LOGIN, pode: () => true, sair: () => {} });

export function usarAcesso(): Acesso {
  return useContext(ContextoDeAcesso);
}

function acessoDe(eu: Eu, sair: () => void): Acesso {
  const permissoes = new Set(eu.permissoes);
  return {
    eu,
    pode: (...pedidas) => eu.administrador || pedidas.length === 0 || pedidas.some((p) => permissoes.has(p)),
    sair,
  };
}

/** Dá à tela um "quem entrou" fixo, sem passar pela Microsoft: para os testes e para telas avulsas. */
export function ProvedorDeAcesso({ eu, children }: { eu: Eu; children: ReactNode }) {
  return <ContextoDeAcesso.Provider value={acessoDe(eu, () => {})}>{children}</ContextoDeAcesso.Provider>;
}

/** O título da tela de entrada (axe: page-has-heading-one). O `h1` herda o peso e não ganha margem,
 * para ficar igual à marca de antes; o espaço antes do "CRM" só existe para o nome acessível. */
function Marca() {
  return (
    <h1 className="login-marca">
      Critério{" "}
      <span>CRM</span>
    </h1>
  );
}

function LogoMicrosoft() {
  return (
    <span className="login-ms" aria-hidden="true">
      <i /><i /><i /><i />
    </span>
  );
}

/** Formulário de e-mail e senha. Devolve à `Entrada` o pedido de entrar; a resposta é o motivo da
 * recusa (para mostrar) ou `null` quando entrou. */
function FormularioDeSenha({ aviso, aoEntrar }: { aviso?: string; aoEntrar: (email: string, senha: string) => Promise<string | null> }) {
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [enviando, definirEnviando] = useState(false);
  const campoEmail = useRef<HTMLInputElement>(null);
  const campoSenha = useRef<HTMLInputElement>(null);

  useEffect(() => {
    campoEmail.current?.focus();
  }, []);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (enviando) return;
    if (!email.trim() || !senha) {
      definirErro("Preencha o e-mail e a senha.");
      (email.trim() ? campoSenha : campoEmail).current?.focus();
      return;
    }
    definirErro(null);
    definirEnviando(true);
    const recusa = await aoEntrar(email.trim(), senha);
    if (recusa === null) return; // entrou: esta tela sai de cena
    definirErro(recusa);
    definirEnviando(false);
    campoSenha.current?.focus();
  };

  return (
    <>
      <form className="login-form" onSubmit={enviar} noValidate aria-label="Entrar no CRM">
        {aviso && !erro && <p className="login-erro" role="alert">{aviso}</p>}
        <div className="campo">
          <label className="campo-rotulo" htmlFor="login-email">E-mail</label>
          <input id="login-email" ref={campoEmail} className="entrada" type="email" inputMode="email" autoComplete="username"
            autoCapitalize="none" spellCheck={false} required value={email} onChange={(e) => definirEmail(e.target.value)}
            aria-invalid={erro ? true : undefined} aria-describedby={erro ? "login-erro" : undefined} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="login-senha">Senha</label>
          <CampoDeSenha id="login-senha" campoRef={campoSenha} valor={senha} aoMudar={definirSenha} autoComplete="current-password" exigido
            descritoPor={erro ? "login-erro" : undefined} />
        </div>
        {erro && <p className="login-erro" id="login-erro" role="alert">✗ {erro}</p>}
        <button type="submit" className="login-botao" disabled={enviando} aria-busy={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p className="login-nota">Esqueceu a senha? Peça a quem administra o CRM para redefinir.</p>
    </>
  );
}

type Fase =
  | { tipo: "carregando" }
  | { tipo: "entrar"; aviso?: string }
  | { tipo: "senha"; aviso?: string }
  | { tipo: "sem_acesso"; mensagem: string }
  | { tipo: "erro"; mensagem: string }
  | { tipo: "dentro"; eu: Eu };

export function Entrada({ children }: { children: ReactNode }) {
  const [fase, definirFase] = useState<Fase>({ tipo: "carregando" });
  const msal = useRef<{ app: PublicClientApplication; escopo: string } | null>(null);
  const modo = useRef<ConfiguracaoDeEntrada["modo"] | null>(null);

  /** Sessão de senha perdida (401 numa rota protegida, ou vencida): apaga o token e volta ao formulário. */
  const perderSessao = (aviso?: string) => {
    apagarSessao();
    definirEntrada(null);
    definirFase({ tipo: "senha", aviso });
  };

  /** Os pedidos passam a levar o token da sessão em uso (`sessaoAtual`), que a troca de senha pode
   * renovar com a página aberta. Vencida, nem sai com ela: a sessão cai antes. */
  const ligarSessao = (sessao: SessaoGuardada) => {
    guardarSessao(sessao);
    definirEntrada(
      async () => {
        const atual = sessaoAtual();
        if (atual && !sessaoVencida(atual)) return atual.token;
        perderSessao(SESSAO_EXPIROU);
        return null;
      },
      () => perderSessao(SESSAO_EXPIROU),
    );
  };

  const entrarComSenha = async (email: string, senha: string): Promise<string | null> => {
    let sessao: SessaoGuardada | null = null;
    try {
      const aberta = await api.login(email, senha);
      sessao = { token: aberta.token, expira_em: aberta.expira_em };
      ligarSessao(sessao);
      const eu = await api.eu();
      definirFase({ tipo: "dentro", eu });
      return null;
    } catch (falha) {
      if (sessao) {
        apagarSessao();
        definirEntrada(null);
      }
      return falha instanceof ErroDaApi ? falha.message : "Não consegui entrar. Tente de novo.";
    }
  };

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const config = await api.entrada();
        modo.current = config.modo;
        if (config.modo === "senha") {
          const sessao = lerSessao();
          if (!sessao || sessaoVencida(sessao)) {
            apagarSessao();
            definirEntrada(null);
            if (vivo) definirFase({ tipo: "senha", aviso: sessao ? SESSAO_EXPIROU : undefined });
            return;
          }
          ligarSessao(sessao);
          const eu = await api.eu();
          if (vivo) definirFase({ tipo: "dentro", eu });
          return;
        }
        if (config.modo !== "microsoft" || !config.client_id || !config.tenant_id || !config.escopo) {
          definirEntrada(null);
          const eu = await api.eu();
          if (vivo) definirFase({ tipo: "dentro", eu });
          return;
        }
        // A biblioteca da Microsoft só baixa quando o login está ligado.
        const { InteractionRequiredAuthError, PublicClientApplication } = await import("@azure/msal-browser");
        const app = new PublicClientApplication({
          auth: {
            clientId: config.client_id,
            authority: `https://login.microsoftonline.com/${config.tenant_id}`,
            redirectUri: `${window.location.origin}/`,
          },
          cache: { cacheLocation: "sessionStorage" },
        });
        await app.initialize();
        msal.current = { app, escopo: config.escopo };
        const volta = await app.handleRedirectPromise();
        const conta: AccountInfo | undefined = volta?.account ?? app.getAllAccounts()[0];
        if (!conta) {
          if (vivo) definirFase({ tipo: "entrar" });
          return;
        }
        app.setActiveAccount(conta);
        const escopos = [config.escopo];
        definirEntrada(
          async () => {
            try {
              return (await app.acquireTokenSilent({ scopes: escopos, account: conta })).accessToken;
            } catch (falha) {
              if (falha instanceof InteractionRequiredAuthError) await app.acquireTokenRedirect({ scopes: escopos });
              throw falha;
            }
          },
          () => definirFase({ tipo: "entrar", aviso: "A sua entrada expirou. Entre de novo." }),
        );
        const eu = await api.eu();
        if (vivo) definirFase({ tipo: "dentro", eu });
      } catch (falha) {
        if (!vivo) return;
        if (modo.current === "senha" && falha instanceof ErroDaApi && (falha.status === 401 || falha.status === 403)) {
          // 401: a sessão guardada já caiu (perderSessao). 403: a conta foi desativada; volta ao formulário com o motivo.
          if (falha.status === 403) perderSessao(falha.message);
          return;
        }
        if (falha instanceof ErroDaApi && falha.status === 403) definirFase({ tipo: "sem_acesso", mensagem: falha.message });
        else definirFase({ tipo: "erro", mensagem: falha instanceof ErroDaApi ? falha.message : "Não consegui abrir o CRM." });
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  const entrar = () => {
    if (msal.current) void msal.current.app.loginRedirect({ scopes: [msal.current.escopo], prompt: "select_account" });
  };
  const sair = () => {
    definirEntrada(null);
    if (modo.current === "senha") {
      apagarSessao();
      definirFase({ tipo: "senha" });
      return;
    }
    if (msal.current) void msal.current.app.logoutRedirect({ postLogoutRedirectUri: `${window.location.origin}/` });
  };

  if (fase.tipo === "dentro") {
    return <ContextoDeAcesso.Provider value={acessoDe(fase.eu, sair)}>{children}</ContextoDeAcesso.Provider>;
  }

  return (
    <main className="login">
      <div className="login-caixa">
        <Marca />
        {fase.tipo === "carregando" && <p className="login-nota" role="status">Abrindo o CRM…</p>}
        {fase.tipo === "senha" && <FormularioDeSenha aviso={fase.aviso} aoEntrar={entrarComSenha} />}
        {fase.tipo === "entrar" && (
          <>
            {fase.aviso && <p className="login-erro" role="alert">{fase.aviso}</p>}
            <button type="button" className="login-botao" onClick={entrar}>
              <LogoMicrosoft />
              Entrar com a conta Microsoft
            </button>
            <p className="login-nota">
              Use a sua conta @grupocriterio.com.br. O CRM não guarda senha: a Microsoft confere quem é você.
            </p>
          </>
        )}
        {fase.tipo === "sem_acesso" && (
          <>
            <p className="login-erro" role="alert">✗ {fase.mensagem}</p>
            <button type="button" className="login-botao" onClick={entrar}>
              Entrar com outra conta
            </button>
          </>
        )}
        {fase.tipo === "erro" && (
          <>
            <p className="login-erro" role="alert">✗ {fase.mensagem}</p>
            <button type="button" className="login-botao" onClick={() => window.location.reload()}>
              Tentar de novo
            </button>
          </>
        )}
      </div>
    </main>
  );
}

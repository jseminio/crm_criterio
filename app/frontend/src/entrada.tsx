/** Entrada no CRM pela conta Microsoft (E1, amostra aprovada por Eduardo em 02/10/2026).
 *
 * A API diz como entrar (`/api/acesso/entrada`). Com a Microsoft configurada, a pessoa entra pelo
 * Microsoft Entra (MSAL, com redirecionamento) e cada pedido leva o token. A Microsoft confere quem
 * é; o CRM decide o que pode (`/api/eu`, com as permissões do perfil). Sem a configuração, o CRM
 * segue sem login, como antes do E1, e a tela avisa.
 */

import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, definirEntrada, ErroDaApi } from "./api/cliente";
import type { Eu } from "./api/tipos";

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

function Marca() {
  return (
    <div className="login-marca">
      Critério
      <span>CRM</span>
    </div>
  );
}

function LogoMicrosoft() {
  return (
    <span className="login-ms" aria-hidden="true">
      <i /><i /><i /><i />
    </span>
  );
}

type Fase =
  | { tipo: "carregando" }
  | { tipo: "entrar"; aviso?: string }
  | { tipo: "sem_acesso"; mensagem: string }
  | { tipo: "erro"; mensagem: string }
  | { tipo: "dentro"; eu: Eu };

export function Entrada({ children }: { children: ReactNode }) {
  const [fase, definirFase] = useState<Fase>({ tipo: "carregando" });
  const msal = useRef<{ app: PublicClientApplication; escopo: string } | null>(null);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const config = await api.entrada();
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

/** O CRM da Critério: navegação, cabeçalho e as quatro telas do E3. */

import { useEffect, useState } from "react";
import "./tokens.css";
import "./app.css";
import { api } from "./api/cliente";
import { usarAcesso } from "./entrada";
import type { Listas } from "./api/tipos";
import { Agenda } from "./telas/Agenda";
import { Contatos } from "./telas/Contatos";
import { Configuracoes } from "./telas/Configuracoes";
import { SdrEAbordagens } from "./telas/SdrEAbordagens";
import { FunilEQuestionarios } from "./telas/FunilEQuestionarios";
import { SucessoDoCliente, type AbaDoSucesso } from "./telas/SucessoDoCliente";
import { AjustesDaAreaTecnica } from "./componentes/AjustesDaAreaTecnica";
import { TrocarSenha } from "./componentes/TrocarSenha";
import { usarDados } from "./usarDados";
import { VERSAO } from "./versao";

type Tela =
  | "agenda"
  | "contatos"
  | "funil"
  | "carteira"
  | "abordagens"
  | "configuracoes";

const TELAS: { chave: Tela; rotulo: string; titulo: string; descricao: string }[] = [
  {
    chave: "agenda",
    rotulo: "Agenda",
    titulo: "Agenda de follow-up",
    descricao: "O que pede uma próxima ação agora, por urgência.",
  },
  {
    chave: "contatos",
    rotulo: "Contatos",
    titulo: "Contatos",
    descricao: "Quem falar em cada empresa: clientes e prospects separados.",
  },
  {
    chave: "funil",
    rotulo: "Funil comercial",
    titulo: "Funil comercial",
    descricao: "Oportunidades em kanban ou grade, e os questionários que chegaram pelo site.",
  },
  {
    chave: "carteira",
    rotulo: "Sucesso do Cliente",
    titulo: "Sucesso do Cliente",
    descricao: "A saúde da carteira, a gestão dos contratos e o funil do sucesso do cliente.",
  },
  {
    chave: "abordagens",
    rotulo: "SDR - Abordagens e conhecimento",
    titulo: "SDR · Abordagens e conhecimento",
    descricao: "A prospecção do agente SDR e a qualificação de leads pela SDR de IA.",
  },
  {
    chave: "configuracoes",
    rotulo: "Configurações",
    titulo: "Configurações",
    descricao: "Perfis e acesso, metas, propostas, integrações, grupos, conferência da carga, histórico, backup e serviços pedidos.",
  },
];

export default function App() {
  const { eu, pode, sair } = usarAcesso();
  // Menu sem nenhuma funcionalidade liberada no perfil não aparece (E1, 02/10/2026).
  const visiveis = TELAS.filter((t) =>
    t.chave === "configuracoes"
      ? pode("configuracoes.propostas", "configuracoes.backup", "configuracoes.perfis", "configuracoes.historico", "configuracoes.metas",
          "grupos.ver", "conferencia.ver")
      : t.chave === "abordagens"
        ? pode("abordagens.ver", "sdr.ver")
        : t.chave === "funil"
          ? pode("funil.ver", "questionarios.ver")
          : t.chave === "carteira"
            ? pode("carteira.ver", "contratos.ver", "sucesso.ver")
            : t.chave === "agenda"
              ? pode("agenda.ver", "ajustes.ver", "ajustes.concluir")
              : pode(`${t.chave}.ver`),
  );
  const [escolhida, definirTela] = useState<Tela>("funil");
  const [trocandoSenha, definirTrocandoSenha] = useState(false);
  // Celular (06/10/2026): o menu lateral vira gaveta, aberta pelo ☰ da faixa do título. No computador
  // a gaveta não existe — o CSS mantém o menu fixo à esquerda e esconde o ☰.
  const [menuAberto, definirMenuAberto] = useState(false);
  // Atalho de outra tela para uma aba (a Agenda abre os contratos): a aba pedida e uma chave para reabrir.
  const [abaDoSucesso, definirAbaDoSucesso] = useState<{ aba: AbaDoSucesso; vez: number } | null>(null);
  const tela = visiveis.some((t) => t.chave === escolhida) ? escolhida : (visiveis[0]?.chave ?? escolhida);
  const { dados: listas } = usarDados<Listas>(() => api.listas(), []);
  const atual = TELAS.find((t) => t.chave === tela)!;

  useEffect(() => {
    if (!menuAberto) return;
    // Esc fecha: quem abriu com teclado precisa sair com teclado.
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") definirMenuAberto(false);
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [menuAberto]);

  return (
    <div className="aplicacao">
      {menuAberto && <div className="cortina-do-menu" onClick={() => definirMenuAberto(false)} aria-hidden="true" />}
      <nav id="navegacao-principal" className={`lateral ${menuAberto ? "lateral-aberta" : ""}`} aria-label="Navegação principal">
        {/* Regra 8 do PAD-002: a logomarca aparece sozinha. Sem o arquivo
            oficial, o nome é composto — nunca redesenhado. O ✕ da gaveta fica
            no rodapé do menu, longe da marca. */}
        <div className="marca">
          Critério
          <span className="marca-linha2">CRM</span>
          <span className="marca-versao">Versão {VERSAO}</span>
        </div>

        <div className="menu">
          {visiveis.map((t) => (
            <button
              key={t.chave}
              type="button"
              className="menu-item"
              aria-current={tela === t.chave ? "page" : undefined}
              onClick={() => {
                definirTela(t.chave);
                definirMenuAberto(false);
              }}
            >
              {t.rotulo}
            </button>
          ))}
        </div>

        {eu.modo !== "local" ? (
          <div className="quem-entrou">
            <strong>{eu.nome ?? eu.email}</strong>
            <span>Perfil: {eu.perfil}</span>
            <div className="quem-entrou-acoes">
              {eu.modo === "senha" && (
                <button type="button" className="quem-entrou-sair" onClick={() => {
                  definirTrocandoSenha(true);
                  definirMenuAberto(false);
                }}>Trocar senha</button>
              )}
              <button type="button" className="quem-entrou-sair" onClick={sair}>Sair</button>
            </div>
          </div>
        ) : (
          <p className="aviso-sem-login">
            Ambiente local, sem login. Não abra esta porta na rede antes da conta corporativa
            existir.
          </p>
        )}
        <button type="button" className="fechar-menu" onClick={() => definirMenuAberto(false)}>
          Fechar menu
        </button>
      </nav>
      {trocandoSenha && <TrocarSenha aoFechar={() => definirTrocandoSenha(false)} />}

      <div className="conteudo">
        <header className="topo">
          <button
            type="button"
            className="botao-menu"
            aria-label="Abrir menu"
            aria-expanded={menuAberto}
            aria-controls="navegacao-principal"
            onClick={() => definirMenuAberto(true)}
          >
            ☰
          </button>
          <h1>{atual.titulo}</h1>
          <p className="topo-detalhe">{atual.descricao}</p>
        </header>

        <main className="area">
          {visiveis.length === 0 && (
            <p className="estado estado-texto" role="status">
              O seu perfil ({eu.perfil}) ainda não libera nenhum menu. Peça a quem administra em Configurações › Perfis e acesso.
            </p>
          )}
          {visiveis.length > 0 && tela === "agenda" && pode("ajustes.ver", "ajustes.concluir") && <AjustesDaAreaTecnica />}
          {visiveis.length > 0 && tela === "agenda" && pode("agenda.ver") && <Agenda
              listas={listas}
              aoAbrirLeads={() => definirTela("funil")}
              aoAbrirContratos={() => {
                definirAbaDoSucesso((a) => ({ aba: "contratos", vez: (a?.vez ?? 0) + 1 }));
                definirTela("carteira");
              }}
            />}
          {visiveis.length > 0 && tela === "contatos" && <Contatos listas={listas} />}
          {visiveis.length > 0 && tela === "funil" && <FunilEQuestionarios listas={listas} />}
          {visiveis.length > 0 && tela === "carteira" && (
            <SucessoDoCliente key={abaDoSucesso?.vez ?? 0} listas={listas} abaPedida={abaDoSucesso?.aba ?? null} />
          )}
          {visiveis.length > 0 && tela === "abordagens" && <SdrEAbordagens listas={listas} />}
          {visiveis.length > 0 && tela === "configuracoes" && <Configuracoes listas={listas} />}
        </main>
      </div>
    </div>
  );
}

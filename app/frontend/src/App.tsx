/** O CRM da Critério: navegação, cabeçalho e as quatro telas do E3. */

import { useState } from "react";
import "./tokens.css";
import "./app.css";
import { api } from "./api/cliente";
import type { Listas } from "./api/tipos";
import { Abordagens } from "./telas/Abordagens";
import { Agenda } from "./telas/Agenda";
import { Conferencia } from "./telas/Conferencia";
import { Carteira } from "./telas/Carteira";
import { Contatos } from "./telas/Contatos";
import { Configuracoes } from "./telas/Configuracoes";
import { Contratos } from "./telas/Contratos";
import { Funil } from "./telas/Funil";
import { Grupos } from "./telas/Grupos";
import { Sdr } from "./telas/Sdr";
import { usarDados } from "./usarDados";
import { VERSAO } from "./versao";

type Tela =
  | "agenda"
  | "contatos"
  | "funil"
  | "grupos"
  | "contratos"
  | "carteira"
  | "abordagens"
  | "sdr"
  | "conferencia"
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
    rotulo: "Funil",
    titulo: "Funil comercial",
    descricao: "Kanban ou grade — arraste um cartão ou abra a linha para mover a oportunidade.",
  },
  {
    chave: "grupos",
    rotulo: "Grupos",
    titulo: "Grupos econômicos",
    descricao: "O cliente é o grupo. Junte os que a planilha separou.",
  },
  {
    chave: "contratos",
    rotulo: "Contratos",
    titulo: "Contratos",
    descricao: "O que a oportunidade aceita virou — começo da Etapa 2.",
  },
  {
    chave: "carteira",
    rotulo: "Carteira",
    titulo: "Classificação da carteira",
    descricao: "Classe, Score e eixo de ação por grupo, e o índice de saúde (ISC).",
  },
  {
    chave: "abordagens",
    rotulo: "Abordagens",
    titulo: "Abordagens",
    descricao: "O agente SDR prepara a ficha e o rascunho. Nada sai sem a sua aprovação.",
  },
  {
    chave: "sdr",
    rotulo: "SDR da IA",
    titulo: "Qualificação pela IA",
    descricao: "Leads de tráfego pago e frios: quantos a IA qualificou, descartou ou passou para a equipe.",
  },
  {
    chave: "conferencia",
    rotulo: "Conferência",
    titulo: "Conferência da carga",
    descricao: "O que entrou da planilha, o que ficou pendente e o que foi ajustado.",
  },
  {
    chave: "configuracoes",
    rotulo: "Configurações",
    titulo: "Configurações",
    descricao: "Backup lógico dos dados e os pedidos de serviço fora do catálogo.",
  },
];

export default function App() {
  const [tela, definirTela] = useState<Tela>("funil");
  const { dados: listas } = usarDados<Listas>(() => api.listas(), []);
  const atual = TELAS.find((t) => t.chave === tela)!;

  return (
    <div className="aplicacao">
      <nav className="lateral" aria-label="Navegação principal">
        {/* Regra 8 do PAD-002: a logomarca aparece sozinha. Sem o arquivo
            oficial, o nome é composto — nunca redesenhado. */}
        <div className="marca">
          Critério
          <span className="marca-linha2">CRM</span>
          <span className="marca-versao">Versão {VERSAO}</span>
        </div>

        <div className="menu">
          {TELAS.map((t) => (
            <button
              key={t.chave}
              type="button"
              className="menu-item"
              aria-current={tela === t.chave ? "page" : undefined}
              onClick={() => definirTela(t.chave)}
            >
              {t.rotulo}
            </button>
          ))}
        </div>

        <p className="aviso-sem-login">
          Ambiente local, sem login. Não abra esta porta na rede antes da conta corporativa
          existir.
        </p>
      </nav>

      <div className="conteudo">
        <header className="topo">
          <h1>{atual.titulo}</h1>
          <p className="topo-detalhe">{atual.descricao}</p>
        </header>

        <main className="area">
          {tela === "agenda" && <Agenda
              listas={listas}
              aoAbrirLeads={() => definirTela("funil")}
              aoAbrirContratos={() => definirTela("contratos")}
            />}
          {tela === "contatos" && <Contatos listas={listas} />}
          {tela === "funil" && <Funil listas={listas} />}
          {tela === "grupos" && <Grupos listas={listas} />}
          {tela === "contratos" && <Contratos listas={listas} />}
          {tela === "carteira" && <Carteira listas={listas} />}
          {tela === "abordagens" && <Abordagens />}
          {tela === "sdr" && <Sdr listas={listas} />}
          {tela === "conferencia" && <Conferencia listas={listas} />}
          {tela === "configuracoes" && <Configuracoes />}
        </main>
      </div>
    </div>
  );
}

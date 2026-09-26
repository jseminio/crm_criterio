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
import { Leads } from "./telas/Leads";
import { Lista } from "./telas/Lista";
import { usarDados } from "./usarDados";

type Tela =
  | "agenda"
  | "contatos"
  | "funil"
  | "lista"
  | "leads"
  | "grupos"
  | "contratos"
  | "carteira"
  | "abordagens"
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
    descricao: "Arraste o olho pelas etapas; clique num cartão para mover a oportunidade.",
  },
  {
    chave: "lista",
    rotulo: "Oportunidades",
    titulo: "Oportunidades",
    descricao: "A mesma base do funil, em lista, para comparar e filtrar.",
  },
  {
    chave: "leads",
    rotulo: "Leads",
    titulo: "Leads",
    descricao: "A porta de entrada do funil. Converta quando virar proposta.",
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
    chave: "conferencia",
    rotulo: "Conferência",
    titulo: "Conferência da carga",
    descricao: "O que entrou da planilha, o que ficou pendente e o que foi ajustado.",
  },
  {
    chave: "configuracoes",
    rotulo: "Configurações",
    titulo: "Configurações",
    descricao: "Backup lógico: leve os dados para outra máquina ou guarde uma cópia.",
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
              aoAbrirLeads={() => definirTela("leads")}
              aoAbrirContratos={() => definirTela("contratos")}
            />}
          {tela === "contatos" && <Contatos listas={listas} />}
          {tela === "funil" && <Funil listas={listas} />}
          {tela === "lista" && <Lista listas={listas} />}
          {tela === "leads" && <Leads listas={listas} />}
          {tela === "grupos" && <Grupos listas={listas} />}
          {tela === "contratos" && <Contratos listas={listas} />}
          {tela === "carteira" && <Carteira />}
          {tela === "abordagens" && <Abordagens />}
          {tela === "conferencia" && <Conferencia />}
          {tela === "configuracoes" && <Configuracoes />}
        </main>
      </div>
    </div>
  );
}

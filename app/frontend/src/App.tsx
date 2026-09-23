/** O CRM da Critério: navegação, cabeçalho e as quatro telas do E3. */

import { useState } from "react";
import "./tokens.css";
import "./app.css";
import { api } from "./api/cliente";
import type { Listas } from "./api/tipos";
import { Conferencia } from "./telas/Conferencia";
import { Configuracoes } from "./telas/Configuracoes";
import { Contratos } from "./telas/Contratos";
import { Funil } from "./telas/Funil";
import { Grupos } from "./telas/Grupos";
import { Leads } from "./telas/Leads";
import { Lista } from "./telas/Lista";
import { usarDados } from "./usarDados";

type Tela = "funil" | "lista" | "leads" | "grupos" | "contratos" | "conferencia" | "configuracoes";

const TELAS: { chave: Tela; rotulo: string; titulo: string; descricao: string }[] = [
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
          {tela === "funil" && <Funil listas={listas} />}
          {tela === "lista" && <Lista listas={listas} />}
          {tela === "leads" && <Leads listas={listas} />}
          {tela === "grupos" && <Grupos listas={listas} />}
          {tela === "contratos" && <Contratos listas={listas} />}
          {tela === "conferencia" && <Conferencia />}
          {tela === "configuracoes" && <Configuracoes />}
        </main>
      </div>
    </div>
  );
}

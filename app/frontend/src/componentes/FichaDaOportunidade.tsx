/** Aba "Ficha" da oportunidade (E4, amostra aprovada por Eduardo em 02/10/2026): as nove seções do
 * questionário do site, cada resposta dizendo de onde veio. Corrigir aqui grava como Entrevista, com
 * quem e quando; a resposta original do cliente continua guardada no questionário recebido.
 *
 * Estado nunca só por cor: cada seção diz "✓ 14 de 14", "◐ 3 de 5", "✗ 0 de 7", "fora do escopo".
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CampoDaFicha, Ficha, SecaoDaFicha } from "../api/tipos";
import { data } from "../formato";
import { usarQuemPreenche } from "../quemPreenche";
import { CampoDeData } from "./CampoDeData";
import { Carregando, Erro } from "./estados";

function situacaoDaSecao(s: SecaoDaFicha): { texto: string; tom: string } {
  if (!s.no_escopo) return { texto: "fora do escopo", tom: "neutra" };
  const conta = `${s.respondidas} de ${s.total}`;
  if (s.numero === 9) return { texto: `para a implantação · ${conta}`, tom: "neutra" };
  if (s.total > 0 && s.respondidas === s.total) return { texto: `✓ ${conta}`, tom: "ganho" };
  if (s.respondidas === 0) return { texto: `✗ ${conta}`, tom: "perda" };
  return { texto: `◐ ${conta}`, tom: "espera" };
}

function Origem({ campo, salvando }: { campo: CampoDaFicha; salvando: boolean }) {
  if (salvando) return <span className="ficha-origem">salvando…</span>;
  if (campo.origem === "Entrevista")
    return (
      <span className="ficha-origem">
        <strong>Entrevista</strong> · {campo.por} · {data(campo.em)}
      </span>
    );
  if (campo.origem === "Questionário")
    return (
      <span className="ficha-origem">
        <strong>Questionário</strong> · {data(campo.em)}
      </span>
    );
  return <span className="ficha-origem">· sem resposta</span>;
}

function Pergunta({
  campo,
  aoSalvar,
}: {
  campo: CampoDaFicha;
  aoSalvar: (valor: string | string[] | null) => Promise<string | null>;
}) {
  const inicial = campo.valor;
  const [valor, definirValor] = useState<string | string[] | null>(inicial);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const id = `ficha-${campo.chave}`;

  const salvar = async (novo: string | string[] | null) => {
    if (JSON.stringify(novo ?? null) === JSON.stringify(inicial ?? null)) return;
    definirSalvando(true);
    definirErro(await aoSalvar(novo));
    definirSalvando(false);
  };

  const texto = typeof valor === "string" ? valor : "";
  const lista = Array.isArray(valor) ? valor : [];
  let entrada;
  if (campo.tipo === "varias") {
    entrada = (
      <div className="ficha-opcoes" role="group" aria-labelledby={`${id}-rotulo`}>
        {campo.opcoes.map((o) => (
          <label key={o} className="ficha-opcao">
            <input
              type="checkbox"
              checked={lista.includes(o)}
              onChange={(e) => {
                const nova = e.target.checked ? [...lista, o] : lista.filter((x) => x !== o);
                definirValor(nova);
                void salvar(nova.length ? nova : null);
              }}
            />
            {o}
          </label>
        ))}
      </div>
    );
  } else if (campo.tipo === "uma") {
    entrada = (
      <select
        id={id}
        className="selecao"
        value={texto}
        onChange={(e) => {
          definirValor(e.target.value || null);
          void salvar(e.target.value || null);
        }}
      >
        <option value="">— sem resposta</option>
        {campo.opcoes.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    );
  } else if (campo.tipo === "data") {
    entrada = (
      <CampoDeData
        id={id}
        value={texto}
        aoMudar={(iso) => {
          definirValor(iso || null);
          void salvar(iso || null);
        }}
      />
    );
  } else if (campo.tipo === "texto_longo") {
    entrada = (
      <textarea
        id={id}
        className="entrada"
        rows={2}
        value={texto}
        placeholder="sem resposta"
        onChange={(e) => definirValor(e.target.value)}
        onBlur={() => void salvar(texto.trim() || null)}
      />
    );
  } else {
    entrada = (
      <input
        id={id}
        className="entrada"
        inputMode={campo.tipo === "numero" ? "numeric" : undefined}
        value={texto}
        placeholder="sem resposta"
        onChange={(e) => definirValor(campo.tipo === "numero" ? e.target.value.replace(/\D/g, "") : e.target.value)}
        onBlur={() => void salvar(texto.trim() || null)}
      />
    );
  }

  return (
    <div className={`ficha-pergunta${campo.sub ? " ficha-pergunta-sub" : ""}`}>
      {campo.tipo === "varias" ? (
        <span className="campo-rotulo" id={`${id}-rotulo`}>{campo.rotulo}</span>
      ) : (
        <label className="campo-rotulo" htmlFor={id}>{campo.rotulo}</label>
      )}
      <div className="ficha-valor">
        {entrada}
        <Origem campo={campo} salvando={salvando} />
      </div>
      {erro && <p className="campo-ajuda campo-data-erro" role="alert">✗ {erro}</p>}
    </div>
  );
}

export function FichaDaOportunidade({ oportunidadeId, aoMudar }: { oportunidadeId: number; aoMudar?: () => void }) {
  const [ficha, definirFicha] = useState<Ficha | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [quem, definirQuem] = usarQuemPreenche(ficha?.revisores ?? []);

  const carregar = () => {
    definirErro(null);
    api
      .ficha(oportunidadeId)
      .then(definirFicha)
      .catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha ao abrir a ficha."));
  };
  useEffect(carregar, [oportunidadeId]);

  if (erro && !ficha) return <Erro mensagem={erro} aoTentarDeNovo={carregar} />;
  if (!ficha) return <Carregando rotulo="Abrindo a ficha" />;

  const salvar = (chave: string) => async (valor: string | string[] | null): Promise<string | null> => {
    try {
      definirFicha(await api.corrigirFicha(oportunidadeId, chave, valor, quem));
      aoMudar?.();
      return null;
    } catch (falha) {
      return falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.";
    }
  };
  const percentual = ficha.total ? Math.round((ficha.respondidas / ficha.total) * 100) : 0;

  return (
    <section className="ficha" aria-label="Ficha">
      <div className="recado ficha-resumo">
        <span>
          <strong>{ficha.respondidas} de {ficha.total}</strong> perguntas respondidas
        </span>
        <span className="ficha-barra" aria-hidden="true"><i style={{ width: `${percentual}%` }} /></span>
        <span>
          {ficha.questionario_em
            ? `questionário de ${data(ficha.questionario_em)} · ajustes na entrevista`
            : "sem questionário: o que se preencher aqui vale como Entrevista"}
        </span>
      </div>
      <div className="ficha-quem">
        <label className="campo-rotulo" htmlFor="ficha-quem">Quem preenche</label>
        <select id="ficha-quem" className="selecao" value={quem} onChange={(e) => definirQuem(e.target.value)}>
          {ficha.revisores.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <span className="campo-ajuda">
          Corrigir aqui grava como <strong>Entrevista</strong>, com quem e quando; a resposta original do cliente fica guardada.
        </span>
      </div>

      {ficha.secoes.map((s) => {
        const sit = situacaoDaSecao(s);
        return (
          <details key={s.numero} className="ficha-secao">
            <summary>
              <span className="ficha-secao-nome">
                <small>{s.numero}</small> {s.titulo}
              </span>
              <span className={`etiqueta etiqueta-${sit.tom}`}>{sit.texto}</span>
            </summary>
            <div className="ficha-campos">
              {s.numero === 3 && (
                <p className="campo-ajuda">Os direcionadores do porte se ajustam na aba "Volumetria e porte".</p>
              )}
              {s.campos.map((c) => (
                <Pergunta key={`${c.chave}-${c.em ?? ""}-${JSON.stringify(c.valor)}`} campo={c} aoSalvar={salvar(c.chave)} />
              ))}
            </div>
          </details>
        );
      })}
    </section>
  );
}

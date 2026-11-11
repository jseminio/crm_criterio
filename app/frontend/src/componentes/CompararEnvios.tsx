/** Comparar os envios da mesma empresa (amostra aprovada por Eduardo em 11/11/2026). O questionário tem um link único;
 * quando a empresa envia de novo, nada é substituído: os envios aparecem lado a lado, só os campos que diferem pedem
 * escolha, o vazio de um é preenchido pelo outro, e quem resolve fica com um envio ou importa a mescla. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CampoComparado, ComparacaoDosEnvios } from "../api/tipos";
import { cnpj, dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";
import { PainelLateral } from "./PainelLateral";

export interface EnvioParaComparar {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string;
}

const ROTULO_DO_ESTADO: Record<CampoComparado["estado"], string> = {
  igual: "iguais", diferente: "escolha", completa: "só um preencheu", vazio: "",
};

function nomeDoEnvio(c: ComparacaoDosEnvios, id: number): string {
  const e = c.envios.find((x) => x.id === id);
  return e ? `${e.numero ?? "sem número"} · ${e.contato_nome.split(" ")[0]}` : String(id);
}

export function CompararEnvios({ q, aoFechar, aoResolver }: {
  q: EnvioParaComparar; aoFechar: () => void; aoResolver: (texto: string) => void;
}) {
  const comparacao = usarDados<ComparacaoDosEnvios>(() => api.enviosDaEmpresa(q.id), [q.id]);
  const [escolhas, definirEscolhas] = useState<Record<string, number>>({});
  const [erro, definirErro] = useState<string | null>(null);
  const [enviando, definirEnviando] = useState(false);

  // Começa sugerindo o envio mais novo em cada campo diferente; a pessoa troca o que quiser.
  useEffect(() => {
    if (!comparacao.dados) return;
    const sugeridas: Record<string, number> = {};
    for (const c of comparacao.dados.campos) if (c.estado === "diferente" && c.sugestao !== null) sugeridas[c.chave] = c.sugestao;
    definirEscolhas(sugeridas);
  }, [comparacao.dados]);

  async function fazer(acao: () => Promise<{ o_que_fez: string }>) {
    definirErro(null);
    definirEnviando(true);
    try {
      const r = await acao();
      aoResolver(r.o_que_fez);
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao resolver os envios.");
    } finally {
      definirEnviando(false);
    }
  }

  const c = comparacao.dados;
  const diferentes = c ? c.campos.filter((x) => x.estado === "diferente") : [];
  const todosDe = (id: number) => Object.fromEntries(diferentes.map((x) => [x.chave, id]));
  const anteriores = c ? c.envios.filter((e) => e.id !== q.id) : [];
  const anterior = anteriores[anteriores.length - 1];
  return (
    <PainelLateral
      titulo={`Comparar os envios de ${q.nome_fantasia || q.razao_social}`}
      subtitulo={c ? `CNPJ ${cnpj(q.cnpj)} · ${c.envios.map((e) => `${e.numero ?? "?"} ${e.contato_nome}, ${dataHora(e.recebido_em)}`).join(" · ")}`
        : `CNPJ ${cnpj(q.cnpj)}`}
      aoFechar={aoFechar}
      rodape={
        <>
          {anterior && (
            <button type="button" className="botao botao-secundario" disabled={enviando}
              onClick={() => void fazer(() => anterior.oportunidade_id !== null
                ? api.descartarEnvio(q.id) : api.combinarEnvios(q.id, todosDe(anterior.id)))}>
              Usar só o {anterior.numero ?? "anterior"}
            </button>
          )}
          <button type="button" className="botao botao-secundario" disabled={enviando || !c}
            onClick={() => void fazer(() => api.combinarEnvios(q.id, todosDe(q.id)))}>
            Usar só o {c?.envios.find((e) => e.id === q.id)?.numero ?? "novo"}
          </button>
          <button type="button" className="botao botao-primario" disabled={enviando || !c}
            onClick={() => void fazer(() => api.combinarEnvios(q.id, escolhas))}>
            {enviando ? "Importando…" : "Importar a mescla"}
          </button>
        </>
      }
    >
      {comparacao.carregando && <Carregando rotulo="Juntando os envios desta empresa" />}
      {comparacao.erro && <Erro mensagem={comparacao.erro} aoTentarDeNovo={comparacao.recarregar} />}
      {c && (
        <>
          <p className="campo-ajuda">
            {diferentes.length === 0 ? "Os envios não divergem em nada: o vazio de um é preenchido pelo outro."
              : `${diferentes.length} campo(s) divergem: escolha de qual envio vem cada um. O vazio de um é preenchido pelo outro.`}
          </p>
          <div className="tabela-rolagem">
            <table className="tabela" aria-label="Envios lado a lado">
              <thead>
                <tr>
                  <th>Campo</th>
                  {c.envios.map((e) => <th key={e.id}>{nomeDoEnvio(c, e.id)}</th>)}
                  <th>Usar</th>
                </tr>
              </thead>
              <tbody>
                {c.campos.map((campo) => (
                  <tr key={campo.chave} className={campo.estado === "diferente" ? "comparar-diferente" : undefined}>
                    <td>{campo.rotulo}</td>
                    {c.envios.map((e) => <td key={e.id}>{campo.valores[String(e.id)] ?? "—"}</td>)}
                    <td>
                      {campo.estado === "diferente" ? (
                        <span className="comparar-escolha" role="radiogroup" aria-label={`De qual envio vem ${campo.rotulo}`}>
                          {c.envios.map((e) => (
                            <label key={e.id} className="mescla-troca">
                              <input type="radio" name={`usar-${campo.chave}`} checked={escolhas[campo.chave] === e.id}
                                onChange={() => definirEscolhas((atual) => ({ ...atual, [campo.chave]: e.id }))} />
                              {e.numero ?? "?"}
                            </label>
                          ))}
                        </span>
                      ) : (
                        <span className={campo.estado === "completa" ? "mescla-preenche" : "celula-fonte"}>
                          {campo.estado === "completa" && campo.sugestao !== null
                            ? `${nomeDoEnvio(c, campo.sugestao).split(" · ")[0]} preenche o vazio` : ROTULO_DO_ESTADO[campo.estado]}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="campo-ajuda">
            Porte, complexidade e risco são recalculados com a mescla. Se a empresa já tem oportunidade aberta, o envio
            combinado vai em seguida para a mescla com o card, como sempre. Nenhum envio é apagado.
          </p>
        </>
      )}
      {erro && <p className="estado-texto estado-erro" role="alert">✗ {erro}</p>}
    </PainelLateral>
  );
}

/** O botão que abre a comparação; aparece no lugar de "Mesclar" quando o envio está esperando comparação. */
export function BotaoComparar({ q, aoResolver, classe = "link-de-tabela" }: {
  q: EnvioParaComparar; aoResolver: (texto: string) => void; classe?: string;
}) {
  const [aberto, definirAberto] = useState(false);
  return (
    <>
      <button type="button" className={classe} onClick={(e) => { e.stopPropagation(); definirAberto(true); }}>
        Comparar envios
      </button>
      {aberto && (
        <CompararEnvios q={q} aoFechar={() => definirAberto(false)}
          aoResolver={(texto) => { definirAberto(false); aoResolver(texto); }} />
      )}
    </>
  );
}

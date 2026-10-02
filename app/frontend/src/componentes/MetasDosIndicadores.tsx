/** Configurações › Metas (aprovado por Eduardo em 02/10/2026): a meta e o alerta do MRR e da taxa de
 * conversão, que deixaram de ser fixos no código. O alerta precisa ficar abaixo da meta (o servidor
 * confere); cada mudança vai para o histórico de alterações, com quem mudou. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Metas } from "../api/tipos";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { CampoDeValor } from "./CampoDeValor";
import { Carregando, Erro } from "./estados";

type Rascunho = { mrr: { meta: string | null; alerta: string | null }; conversao: { meta: string | null; alerta: string | null } };

const deMetas = (m: Metas): Rascunho => ({
  mrr: { meta: m.mrr.meta, alerta: m.mrr.alerta },
  conversao: { meta: m.conversao.meta, alerta: m.conversao.alerta },
});

function Ultima({ por, em }: { por: string | null; em: string | null }) {
  if (!em) return <span className="campo-ajuda">Valor do KPI oficial, ainda não alterado</span>;
  return <span className="campo-ajuda">Última mudança: {por ? `${por}, ` : ""}{dataHora(em)}</span>;
}

export function MetasDosIndicadores() {
  const { dados, carregando, erro, recarregar } = usarDados<Metas>(() => api.metas(), []);
  const [rascunho, definirRascunho] = useState<Rascunho | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  if (carregando && !dados) return <Carregando rotulo="Abrindo as metas" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const atual = rascunho ?? deMetas(dados);
  const mudar = (chave: keyof Rascunho, campo: "meta" | "alerta", valor: string | null) => {
    definirFeito(null);
    definirRascunho({ ...atual, [chave]: { ...atual[chave], [campo]: valor } });
  };
  const igual = (a: string | null, b: string) => a !== null && Number(a) === Number(b);
  const mudou =
    !igual(atual.mrr.meta, dados.mrr.meta) || !igual(atual.mrr.alerta, dados.mrr.alerta) ||
    !igual(atual.conversao.meta, dados.conversao.meta) || !igual(atual.conversao.alerta, dados.conversao.alerta);
  const vazio = [atual.mrr.meta, atual.mrr.alerta, atual.conversao.meta, atual.conversao.alerta].some((v) => !v);

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.mudarMetas({
        mrr: { meta: atual.mrr.meta!, alerta: atual.mrr.alerta! },
        conversao: { meta: atual.conversao.meta!, alerta: atual.conversao.alerta! },
      });
      definirRascunho(null);
      recarregar();
      definirFeito("Metas salvas. O MRR e a taxa de conversão já comparam com os valores novos.");
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar as metas.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <section className="numero" aria-labelledby="metas-titulo">
      <h3 className="numero-rotulo" id="metas-titulo">Metas dos indicadores</h3>
      <p className="campo-ajuda">O alerta precisa ficar abaixo da meta. Cada mudança fica no histórico de alterações, com quem mudou.</p>
      <div className="metas">
        <div className="metas-linha">
          <strong>MRR da carteira</strong>
          <label className="metas-campo">
            <span>Meta (R$/mês)</span>
            <CampoDeValor value={atual.mrr.meta} aoMudar={(v) => mudar("mrr", "meta", v)} aria-label="Meta do MRR" />
          </label>
          <label className="metas-campo">
            <span>Alerta abaixo de (R$/mês)</span>
            <CampoDeValor value={atual.mrr.alerta} aoMudar={(v) => mudar("mrr", "alerta", v)} aria-label="Alerta do MRR" />
          </label>
          <Ultima por={dados.mrr.alterado_por} em={dados.mrr.alterado_em} />
        </div>
        <div className="metas-linha">
          <strong>Taxa de conversão</strong>
          <label className="metas-campo">
            <span>Meta (%)</span>
            <CampoDeValor value={atual.conversao.meta} aoMudar={(v) => mudar("conversao", "meta", v)} aria-label="Meta da conversão" />
          </label>
          <label className="metas-campo">
            <span>Alerta abaixo de (%)</span>
            <CampoDeValor value={atual.conversao.alerta} aoMudar={(v) => mudar("conversao", "alerta", v)} aria-label="Alerta da conversão" />
          </label>
          <Ultima por={dados.conversao.alterado_por} em={dados.conversao.alterado_em} />
        </div>
      </div>
      <div className="perfis-acoes">
        <button type="button" className="botao botao-primario" disabled={!mudou || vazio || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar metas"}
        </button>
        {mudou && !vazio && <span className="campo-ajuda">· alterações ainda não salvas</span>}
        {vazio && <span className="campo-ajuda">· preencha os quatro valores</span>}
      </div>
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
    </section>
  );
}

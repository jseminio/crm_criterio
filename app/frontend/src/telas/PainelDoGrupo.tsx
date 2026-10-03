/** O painel de um grupo do Funil do Sucesso do Cliente: na implantação, o checklist da etapa; em curso,
 * as reuniões e a ata (`PainelEmCurso`). */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo } from "../api/tipos";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { PainelEmCurso } from "./PainelEmCurso";

export function PainelDoGrupo({ f, g, tipo, aoFechar, aoMudar }: {
  f: Funil; g: Grupo; tipo: string | null; aoFechar: () => void; aoMudar: () => void;
}) {
  const etapa = f.etapas.find((e) => e.chave === g.etapa);
  const reuniao = g.classe ? (f.cadencia[g.classe] ?? []).map((t) => f.tipos.find((x) => x.chave === t)?.nome.toLowerCase() ?? t).join(", ") : "";
  const subtitulo = g.etapa === "em_curso"
    ? `Em curso${g.classe ? ` · classe ${g.classe} · reunião ${reuniao}` : " · sem classe"}${g.em_curso_desde ? ` · desde ${data(g.em_curso_desde)}` : ""}`
    : `Implantação · ${etapa?.nome}${etapa?.participantes ? ` (${etapa.participantes})` : ""}`;
  return g.etapa === "em_curso"
    ? <PainelEmCurso f={f} g={g} tipoPedido={tipo} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />
    : <Implantacao f={f} g={g} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />;
}

type PropsDoPainel = { f: Funil; g: Grupo; titulo: string; subtitulo: string; aoFechar: () => void; aoMudar: () => void };

function Implantacao({ f, g, titulo, subtitulo, aoFechar, aoMudar }: PropsDoPainel) {
  const { pode } = usarAcesso();
  const edita = pode("sucesso.editar");
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const itens = f.checklist[g.etapa] ?? [];
  const faltam = itens.filter((i) => !g.itens_feitos.includes(i.chave)).length;
  const seguinte = f.etapas[f.etapas.findIndex((e) => e.chave === g.etapa) + 1];

  const fazer = async (acao: () => Promise<unknown>) => {
    definirOcupado(true);
    definirFalha(null);
    try {
      await acao();
      aoMudar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui gravar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <PainelLateral
      titulo={titulo} subtitulo={subtitulo} aoFechar={aoFechar}
      rodape={edita ? (
        <>
          <button type="button" className="botao botao-primario" disabled={faltam > 0 || ocupado}
            onClick={() => void fazer(() => api.concluirEtapaDoSucesso(g.grupo_id))}>
            Concluir etapa e passar para {seguinte?.nome}
          </button>
          {faltam > 0 && <span className="campo-ajuda">· faltam {faltam} {faltam === 1 ? "item" : "itens"}</span>}
        </>
      ) : undefined}
    >
      <fieldset className="sucesso-checklist" disabled={!edita || ocupado}>
        <legend className="campo-rotulo">Checklist da etapa</legend>
        {itens.map((i) => (
          <label key={i.chave}>
            <input type="checkbox" checked={g.itens_feitos.includes(i.chave)}
              onChange={(e) => void fazer(() => api.marcarItemDoSucesso(g.grupo_id, i.chave, e.target.checked))} />
            {i.rotulo}
          </label>
        ))}
      </fieldset>
      {g.etapa === "kickoff" && (
        <p className="campo-ajuda">Ao concluir o kickoff, o grupo entra em curso e as reuniões de resultado passam a contar a partir de hoje.</p>
      )}
      {!edita && <p className="campo-ajuda">O seu perfil só vê: marcar itens pede "Funil do Sucesso do Cliente: marcar etapas e registrar reuniões".</p>}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
    </PainelLateral>
  );
}

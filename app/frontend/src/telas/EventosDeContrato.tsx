/** Eventos do contrato: aditivo, reajuste, expansão, contração, renovação, encerramento.
 *
 * **A vigência começa na assinatura** (decisão de 25/09/2026), então só contrato
 * assinado recebe evento. Cada evento é um **fato imutável**: depois de registrado
 * não se edita nem se apaga — errou, registra outro. Por isso o registro pede
 * confirmação em dois passos, e o painel deixa claro o que vai mudar no contrato.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoDetalhe, EventoDeContrato } from "../api/tipos";
import { data, dataHora, dinheiro } from "../formato";

type Tipo = EventoDeContrato["tipo"];
const TIPOS: { valor: Tipo; ajuda: string }[] = [
  { valor: "Reajuste", ajuda: "Troca o preço (para cima ou para baixo), por correção ou negociação." },
  { valor: "Expansão", ajuda: "O cliente contrata mais: o novo preço não pode ser menor." },
  { valor: "Contração", ajuda: "O cliente reduz o escopo: o novo preço não pode ser maior." },
  { valor: "Aditivo", ajuda: "Qualquer alteração contratual. Descreva o que mudou; escopo e preço são opcionais." },
  { valor: "Renovação", ajuda: "Estende a vigência: informe a nova data de fim." },
  { valor: "Encerramento", ajuda: "Encerra o contrato. O motivo é obrigatório e alimenta a análise de saída." },
];

const PRECOS: Tipo[] = ["Reajuste", "Expansão", "Contração", "Aditivo"];

function Efeito({ e }: { e: EventoDeContrato }) {
  const partes: string[] = [];
  if (e.preco_mensal_novo !== null)
    partes.push(`mensal ${dinheiro(e.preco_mensal_anterior)} → ${dinheiro(e.preco_mensal_novo)}`);
  if (e.preco_anual_novo !== null)
    partes.push(`anual ${dinheiro(e.preco_anual_anterior)} → ${dinheiro(e.preco_anual_novo)}`);
  if (e.escopo_novo !== null) partes.push(`escopo “${e.escopo_anterior ?? "—"}” → “${e.escopo_novo}”`);
  if (e.data_fim_nova !== null)
    partes.push(`fim ${e.data_fim_anterior ? data(e.data_fim_anterior) : "—"} → ${data(e.data_fim_nova)}`);
  return <>{partes.length ? partes.join(" · ") : "sem mudança de valores"}</>;
}

export function EventosDeContrato({
  contrato,
  aoRegistrar,
}: {
  contrato: ContratoDetalhe;
  aoRegistrar: (atualizado: ContratoDetalhe) => void;
}) {
  const assinado = contrato.situacao === "Ativo" || contrato.situacao === "Suspenso";
  const [tipo, definirTipo] = useState<Tipo>("Reajuste");
  const [campos, definirCampos] = useState<Record<string, string>>({});
  const [confirmando, definirConfirmando] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const mudar = (campo: string, valor: string) => {
    definirCampos((c) => ({ ...c, [campo]: valor }));
    definirConfirmando(false);
  };
  const ajuda = TIPOS.find((t) => t.valor === tipo)!.ajuda;
  const pedeMotivo = tipo === "Encerramento";
  const pedeDescricao = tipo === "Aditivo" || pedeMotivo;
  const faltaDado =
    (pedeDescricao && (campos.descricao ?? "").trim().length < 3) ||
    (tipo === "Renovação" && !campos.data_fim_nova) ||
    (["Reajuste", "Expansão", "Contração"].includes(tipo) && !campos.preco_mensal_novo && !campos.preco_anual_novo);

  const registrar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo: Record<string, unknown> = { tipo, data_do_evento: campos.data_do_evento || null };
      for (const k of ["descricao", "escopo_novo", "preco_mensal_novo", "preco_anual_novo", "data_fim_nova"]) {
        if (campos[k]) corpo[k] = campos[k];
      }
      const atualizado = await api.registrarEventoDeContrato(contrato.id, corpo);
      definirCampos({});
      definirConfirmando(false);
      aoRegistrar(atualizado);
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao registrar.");
      definirConfirmando(false);
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <div className="formulario">
      <h3 style={{ fontSize: 14, marginBottom: "var(--e2)" }}>Eventos do contrato</h3>

      {contrato.eventos.length === 0 ? (
        <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum evento registrado desde a assinatura.</p>
      ) : (
        <ul className="eventos">
          {contrato.eventos.map((ev) => (
            <li key={ev.id} className="evento">
              <div>
                <strong>{ev.tipo}</strong> · {data(ev.data_do_evento)}
                <span className="numero-nota"> · registrado em {dataHora(ev.registrado_em)}</span>
              </div>
              <div className="numero-nota"><Efeito e={ev} /></div>
              {ev.descricao && <div>{ev.tipo === "Encerramento" ? "Motivo: " : ""}{ev.descricao}</div>}
            </li>
          ))}
        </ul>
      )}

      {!assinado ? (
        <div className="recado">
          {contrato.situacao === "Encerrado"
            ? "Contrato encerrado: não recebe mais eventos."
            : "A vigência começa na assinatura. Informe a data da assinatura e ative o contrato para registrar eventos."}
        </div>
      ) : (
        <>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-tipo">Registrar evento</label>
            <select id="ev-tipo" className="selecao" value={tipo} onChange={(e) => { definirTipo(e.target.value as Tipo); definirConfirmando(false); }}>
              {TIPOS.map((t) => <option key={t.valor} value={t.valor}>{t.valor}</option>)}
            </select>
            <p className="campo-ajuda">{ajuda}</p>
          </div>

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-data">Data do evento (vazio = hoje)</label>
            <input id="ev-data" type="date" className="entrada" value={campos.data_do_evento ?? ""} onChange={(e) => mudar("data_do_evento", e.target.value)} />
          </div>

          {PRECOS.includes(tipo) && (
            <div className="formulario-duplo">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ev-mensal">Novo preço mensal</label>
                <input id="ev-mensal" type="number" step="0.01" min="0" className="entrada" value={campos.preco_mensal_novo ?? ""} onChange={(e) => mudar("preco_mensal_novo", e.target.value)} placeholder={contrato.preco_mensal ?? ""} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ev-anual">Novo preço anual</label>
                <input id="ev-anual" type="number" step="0.01" min="0" className="entrada" value={campos.preco_anual_novo ?? ""} onChange={(e) => mudar("preco_anual_novo", e.target.value)} placeholder={contrato.preco_anual ?? ""} />
              </div>
            </div>
          )}

          {tipo === "Aditivo" && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-escopo">Novo escopo (opcional)</label>
              <input id="ev-escopo" className="entrada" maxLength={200} value={campos.escopo_novo ?? ""} onChange={(e) => mudar("escopo_novo", e.target.value)} placeholder={contrato.escopo ?? ""} />
            </div>
          )}

          {tipo === "Renovação" && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-fim">Nova data de fim</label>
              <input id="ev-fim" type="date" className="entrada" value={campos.data_fim_nova ?? ""} onChange={(e) => mudar("data_fim_nova", e.target.value)} />
              <p className="campo-ajuda">Hoje o contrato termina em {contrato.data_fim ? data(contrato.data_fim) : "— (sem data de fim)"}.</p>
            </div>
          )}

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-desc">
              {pedeMotivo ? "Motivo do encerramento" : pedeDescricao ? "O que foi aditado" : "Motivo (opcional)"}
            </label>
            <input id="ev-desc" className="entrada" maxLength={500} value={campos.descricao ?? ""} onChange={(e) => mudar("descricao", e.target.value)} placeholder={pedeMotivo ? "ex.: o cliente migrou de contador" : "ex.: reajuste anual pelo IPCA"} />
          </div>

          {erro && <p role="alert" className="estado-texto">{erro}</p>}

          {confirmando ? (
            <>
              <div className="recado">
                <strong>Isto não se edita nem se apaga depois.</strong> Se errar, registre outro evento.
                {tipo === "Encerramento" && " O contrato passa a Encerrado e não recebe mais eventos."}
              </div>
              <button type="button" className="botao botao-primario" disabled={salvando} onClick={registrar}>
                {salvando ? "Registrando…" : `Confirmar ${tipo.toLowerCase()}`}
              </button>
            </>
          ) : (
            <button type="button" className="botao botao-secundario" disabled={faltaDado} onClick={() => definirConfirmando(true)}>
              Registrar {tipo.toLowerCase()}
            </button>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Confirmação de "Excluir contrato" (30/10/2026, amostra aprovada por Karine): abre do botão Excluir da
 * lista, diz o que sai junto e o que fica, pede o motivo e só então libera "Excluir de vez". Vale para
 * qualquer situação, inclusive Ativo — por isso o aviso de que ele sai do MRR e dos indicadores.
 */
import { useEffect, useState } from "react";
import { api } from "../api/cliente";
import type { ContratoResumo, ExclusaoDoContrato } from "../api/tipos";
import { dinheiro } from "../formato";
import { Modal } from "./Modal";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

function lista(itens: string[]) {
  return itens.length < 2 ? itens.join("") : `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

export function ExclusaoDeContrato({
  contrato,
  aoFechar,
  aoExcluir,
}: {
  contrato: ContratoResumo;
  aoFechar: () => void;
  aoExcluir: () => void;
}) {
  const [exclusao, definirExclusao] = useState<ExclusaoDoContrato | null>(null);
  const [motivo, definirMotivo] = useState("");
  const [excluindo, definirExcluindo] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  useEffect(() => {
    api.exclusaoDoContrato(contrato.id).then(definirExclusao, (falha) =>
      definirErro(falha instanceof Error ? falha.message : "Falha ao conferir o contrato."),
    );
  }, [contrato.id]);

  const confirmar = async () => {
    definirExcluindo(true);
    definirErro(null);
    try {
      await api.excluirContrato(contrato.id, motivo.trim());
      aoExcluir();
    } catch (falha) {
      definirErro(falha instanceof Error ? falha.message : "Falha ao excluir.");
      definirExcluindo(false);
    }
  };

  const sai = exclusao
    ? ([
        exclusao.eventos && plural(exclusao.eventos, "evento", "eventos"),
        exclusao.pedidos_de_aprovacao &&
          plural(exclusao.pedidos_de_aprovacao, "pedido de aprovação", "pedidos de aprovação"),
        exclusao.documentos_gerados && plural(exclusao.documentos_gerados, "documento gerado", "documentos gerados"),
      ].filter(Boolean) as string[])
    : [];
  const desliga = exclusao
    ? ([
        exclusao.anexos && plural(exclusao.anexos, "PDF anexado", "PDFs anexados"),
        exclusao.envelopes && plural(exclusao.envelopes, "envelope de assinatura", "envelopes de assinatura"),
      ].filter(Boolean) as string[])
    : [];

  return (
    <Modal
      titulo="Excluir contrato"
      subtitulo={[contrato.grupo_nome, contrato.escopo, contrato.preco_mensal && `${dinheiro(contrato.preco_mensal)}/mês`]
        .filter(Boolean)
        .join(" · ")}
      aoFechar={aoFechar}
      rodape={
        <div className="exclusao-acoes" style={{ flex: 1 }}>
          <button type="button" className="botao botao-secundario" onClick={aoFechar} disabled={excluindo}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-perigo"
            onClick={confirmar}
            disabled={excluindo || !exclusao || !motivo.trim()}
          >
            {excluindo ? "Excluindo…" : "Excluir de vez"}
          </button>
        </div>
      }
    >
      <div className="exclusao-caixa" role="group" aria-label="Confirmar exclusão">
        <strong className="exclusao-titulo">
          ⚠ Excluir o contrato {contrato.situacao} de “{contrato.grupo_nome}”?
        </strong>
        {!exclusao && !erro && <p>Conferindo o que sai junto…</p>}
        {exclusao && (
          <>
            <p>
              {sai.length ? (
                <>Sai junto: <b>{lista(sai)}</b>.</>
              ) : (
                "Sai só o contrato: ele não tem evento, pedido de aprovação nem documento gerado."
              )}
            </p>
            <p>
              O contrato some da carteira, do MRR e dos indicadores. Fica: o grupo, a empresa e a oportunidade de
              origem, que continua Aceita e pode virar contrato de novo.
              {desliga.length > 0 && <> Continuam, sem apontar para ele: {lista(desliga)}.</>}
            </p>
          </>
        )}
        <p>Fica registrado no Histórico de alterações quem excluiu, quando e o motivo. Não dá para desfazer pela tela.</p>
        <label className="campo-rotulo" htmlFor="motivo-da-exclusao-do-contrato">Motivo (obrigatório)</label>
        <textarea
          id="motivo-da-exclusao-do-contrato"
          className="entrada"
          rows={2}
          maxLength={1000}
          value={motivo}
          onChange={(ev) => definirMotivo(ev.target.value)}
        />
        {erro && <p role="alert" className="exclusao-erro">⚠ {erro}</p>}
      </div>
    </Modal>
  );
}

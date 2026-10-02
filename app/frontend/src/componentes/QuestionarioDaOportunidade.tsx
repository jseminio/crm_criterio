/** De onde veio a volumetria desta oportunidade, quando ela nasceu (ou recebeu dados) do
 * questionário que o cliente preencheu no site (01/10/2026). Só aparece se houver questionário. */

import { useEffect, useState } from "react";
import { api } from "../api/cliente";
import type { QuestionarioDaOportunidade as Questionario } from "../api/tipos";
import { dataHora } from "../formato";
import { LinkDeArquivo } from "./LinkDeArquivo";

const lista = (fatores: { rotulo: string }[]) => (fatores.length ? fatores.map((f) => f.rotulo).join(", ") : "nenhum fator");

export function QuestionarioDaOportunidade({ oportunidadeId }: { oportunidadeId: number }) {
  const [q, definirQ] = useState<Questionario | null>(null);

  useEffect(() => {
    let vivo = true;
    api.questionarioDaOportunidade(oportunidadeId).then((r) => vivo && definirQ(r)).catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, [oportunidadeId]);

  if (!q) return null;
  return (
    <section className="questionario-da-oportunidade" aria-label="Questionário do cliente">
      <p className="recado">
        Veio do <strong>questionário</strong> enviado em {dataHora(q.recebido_em)} por {q.contato_nome}
        {q.contato_cargo ? `, ${q.contato_cargo}` : ""} (versão {q.versao}).{" "}
        {q.tem_pdf ? (
          <LinkDeArquivo href={`/api/questionarios/${q.id}/pdf`} novaAba>Ver PDF</LinkDeArquivo>
        ) : (
          "Chegou sem PDF."
        )}
      </p>
      <p>
        {q.porte_crm ? (
          <>
            <strong>Porte sugerido pela régua do CRM, com os números do questionário: {q.porte_crm}</strong> · pontuação{" "}
            {q.pontuacao?.replace(".", ",")} · {q.horas_base} h base/mês
            {q.porte_site && q.porte_site !== q.porte_crm ? ` (o questionário dizia ${q.porte_site})` : ""}
          </>
        ) : (
          "O questionário não trouxe volumes: sem porte sugerido."
        )}
      </p>
      {(q.notas_emitidas !== null || q.notas_recebidas !== null) && (
        <p className="campo-ajuda">
          Documentos fiscais/mês = notas emitidas {q.notas_emitidas ?? "—"} + recebidas {q.notas_recebidas ?? "—"}.
        </p>
      )}
      <p>
        Complexidade <strong>{q.nota_complexidade}</strong>: {lista(q.fatores_complexidade)} · Risco técnico{" "}
        <strong>{q.nota_risco}</strong>: {lista(q.fatores_risco)}
      </p>
      {q.servicos.length > 0 && <p className="campo-ajuda">Escopo pedido: {q.servicos.join(", ")}.</p>}
      {q.pontos_de_atencao.length > 0 && (
        <div className="campo-ajuda">
          Pontos de atenção declarados:
          <ul>
            {q.pontos_de_atencao.map(([texto, area]) => <li key={texto}>{area}: {texto}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

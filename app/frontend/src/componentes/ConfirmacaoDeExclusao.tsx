/**
 * Confirmação de "Excluir oportunidade" (04/10/2026, amostra aprovada por Eduardo): diz o que sai
 * junto e o que fica, pede o motivo e só então libera "Excluir de vez". Fica no rodapé do painel,
 * no lugar dos botões de sempre — a ação perigosa é a única forte enquanto ela está aberta.
 */
import { useState } from "react";
import type { ExclusaoDaOportunidade } from "../api/tipos";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

function lista(itens: string[]) {
  return itens.length < 2 ? itens.join("") : `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

export function ConfirmacaoDeExclusao({
  nome,
  exclusao,
  aoCancelar,
  aoExcluir,
}: {
  nome: string;
  exclusao: ExclusaoDaOportunidade;
  aoCancelar: () => void;
  aoExcluir: (motivo: string) => Promise<void>;
}) {
  const [motivo, definirMotivo] = useState("");
  const [excluindo, definirExcluindo] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const sai = [
    exclusao.propostas && plural(exclusao.propostas, "proposta", "propostas"),
    exclusao.pendencias && plural(exclusao.pendencias, "pendência da proposta", "pendências da proposta"),
    exclusao.precos && "o histórico de preço desta oportunidade",
  ].filter(Boolean) as string[];
  const desliga = [
    exclusao.leads && (exclusao.leads === 1 ? "o lead de origem" : plural(exclusao.leads, "lead", "leads")),
    exclusao.questionarios && plural(exclusao.questionarios, "questionário do site", "questionários do site"),
    exclusao.vendas_da_reuniao &&
      plural(exclusao.vendas_da_reuniao, "venda anotada em reunião", "vendas anotadas em reunião"),
  ].filter(Boolean) as string[];

  const confirmar = async () => {
    definirExcluindo(true);
    definirErro(null);
    try {
      await aoExcluir(motivo.trim());
    } catch (falha) {
      definirErro(falha instanceof Error ? falha.message : "Falha ao excluir.");
      definirExcluindo(false);
    }
  };

  return (
    <div className="exclusao">
      <div className="exclusao-caixa" role="group" aria-label="Confirmar exclusão">
        <strong className="exclusao-titulo">⚠ Excluir a oportunidade “{nome}”?</strong>
        <p>
          {sai.length ? (
            <>Sai junto: <b>{lista(sai)}</b>.</>
          ) : (
            "Sai só a oportunidade: ela não tem proposta, pendência nem histórico de preço."
          )}
        </p>
        <p>
          Fica: o grupo, as empresas, os contatos e as reuniões.
          {desliga.length > 0 && <> Continuam, sem apontar para ela: {lista(desliga)}.</>}
        </p>
        {exclusao.sai_da_conversao && <p>Ela sai da taxa de conversão.</p>}
        <p>Fica registrado no Histórico de alterações quem excluiu, quando e o motivo. Não dá para desfazer pela tela.</p>
        <label className="campo-rotulo" htmlFor="motivo-da-exclusao">Motivo (obrigatório)</label>
        <textarea
          id="motivo-da-exclusao"
          className="entrada"
          rows={2}
          maxLength={1000}
          value={motivo}
          onChange={(ev) => definirMotivo(ev.target.value)}
          autoFocus
        />
        {erro && <p role="alert" className="exclusao-erro">⚠ {erro}</p>}
      </div>
      <div className="exclusao-acoes">
        <button type="button" className="botao botao-secundario" onClick={aoCancelar} disabled={excluindo}>
          Cancelar
        </button>
        <button type="button" className="botao botao-perigo" onClick={confirmar} disabled={excluindo || !motivo.trim()}>
          {excluindo ? "Excluindo…" : "Excluir de vez"}
        </button>
      </div>
    </div>
  );
}

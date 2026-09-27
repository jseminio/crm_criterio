/** Os nove direcionadores da régua de porte (`crm.domain.porte`), na ordem de
 * `regua-de-porte-e-plano-de-teste.md`, seção 2. Em branco = "não se aplica ao escopo
 * contratado" — fica fora da média, nunca vira zero. Compartilhado entre a Oportunidade (fase
 * comercial) e a Carteira (avaliação de cliente já ativo): mesma régua, mesmo rótulo. */
export const DIRECIONADORES_DE_PORTE: { id: string; rotulo: string; placeholder: string }[] = [
  { id: "documentos_fiscais_mes", rotulo: "Documentos fiscais/mês", placeholder: "emitidas + recebidas" },
  { id: "lancamentos_contabeis_mes", rotulo: "Lançamentos contábeis/mês", placeholder: "" },
  { id: "pagamentos_mes", rotulo: "Pagamentos/mês", placeholder: "" },
  { id: "contas_bancarias", rotulo: "Contas bancárias", placeholder: "" },
  { id: "conciliacoes_cartao_mes", rotulo: "Conciliações de cartão/mês", placeholder: "0 = nenhuma" },
  { id: "empregados_clt", rotulo: "Empregados CLT", placeholder: "" },
  { id: "admissoes_desligamentos_mes", rotulo: "Admissões + desligamentos/mês", placeholder: "" },
  { id: "cnpjs_no_escopo", rotulo: "CNPJs no escopo", placeholder: "" },
  { id: "tomadores_de_servico", rotulo: "Tomadores de serviço", placeholder: "" },
];

export const PORTES = ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"] as const;

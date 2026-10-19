/** Estado com palavra, nunca só cor — regra 4 do PAD-002.
 *
 * A cor acompanha o texto; quem não distingue as cores lê a palavra e entende
 * o mesmo. Por isso o componente não aceita "só a bolinha".
 */

const TOM_POR_SITUACAO: Record<string, string> = {
  Aceita: "ganho",
  Perdida: "perda",
  "On hold": "espera",
  "Em avaliação pela empresa": "andamento",
  "Enviar proposta": "andamento",
  Novo: "andamento",
  "Em contato": "andamento",
  Qualificado: "ganho",
  Convertido: "ganho",
  Descartado: "perda",
  Cliente: "ganho",
  Prospect: "andamento",
  Encerrado: "perda",
  Fundido: "espera",
  "Aguardando assinatura": "espera",
  Ativo: "ganho",
  // Questionário do site (01/10/2026)
  "cliente novo": "ganho",
  "empresa já no CRM": "andamento",
  "precisa de você": "espera",
  // Configurações › Integrações (07/10/2026)
  Configurado: "ganho",
  "Falta configurar": "espera",
  // Proposta em PowerPoint (01/10/2026)
  "gerada, não enviada": "espera",
  enviada: "ganho",
  Suspenso: "espera",
  "A preparar": "neutra",
  Pesquisando: "andamento",
  "Aguardando aprovação": "espera",
  Aprovada: "andamento",
  Enviada: "ganho",
  Descartada: "neutra",
  Erro: "perda",
  Bloqueada: "perda",
  // Base de conhecimento do SDR de IA (03/10/2026); "Aprovada" já vem das abordagens
  Rascunho: "neutra",
  "Em revisão": "espera",
  Arquivada: "neutra",
  Vencida: "perda",
  // Reajuste anual de julho (13/10/2026)
  Reajustar: "ganho",
  "Você decide": "espera",
  Adiado: "neutra",
  Reajustado: "andamento",
  "Sem reajuste": "neutra",
  "Sem preço": "perda",
  // Parceiros (19/10/2026): o acordo, a etapa da relação e o fee
  "Contrato assinado": "ganho",
  "Contrato em minuta": "andamento",
  "Informal, com fee": "espera",
  "Sem acordo": "perda",
  Mapeado: "neutra",
  Formalizado: "andamento",
  Ativado: "andamento",
  Produtivo: "ganho",
  "Estratégico": "ganho",
  Dormente: "perda",
  "A aprovar": "espera",
  "Aprovado, a pagar": "andamento",
  Pago: "ganho",
  Recusado: "perda",
  // Follow-up de parceiros (19/10/2026): o resultado do follow-up feito
  "Pediu indicação": "andamento",
  "Recebeu indicação": "ganho",
  "Sem novidade": "neutra",
  "Relação em risco": "perda",
};

const TOM_POR_TEMPERATURA: Record<string, string> = {
  Quente: "perda",
  Morno: "espera",
  Frio: "andamento",
};

export function Etiqueta({
  texto,
  tipo = "situacao",
}: {
  texto: string | null | undefined;
  tipo?: "situacao" | "temperatura" | "neutra";
}) {
  if (!texto) return null;
  const tom =
    tipo === "temperatura"
      ? (TOM_POR_TEMPERATURA[texto] ?? "neutra")
      : tipo === "neutra"
        ? "neutra"
        : (TOM_POR_SITUACAO[texto] ?? "neutra");
  return <span className={`etiqueta etiqueta-${tom}`}>{texto}</span>;
}

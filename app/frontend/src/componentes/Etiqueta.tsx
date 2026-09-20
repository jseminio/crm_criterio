/** Estado com palavra, nunca só cor — regra 4 do PAD-002.
 *
 * A cor acompanha o texto; quem não distingue as cores lê a palavra e entende
 * o mesmo. Por isso o componente não aceita "só a bolinha".
 */

const TOM_POR_SITUACAO: Record<string, string> = {
  Aceita: "ganho",
  Recusada: "perda",
  Perdido: "perda",
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

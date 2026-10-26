/** O "i" ao lado de Nível no painel do parceiro (21/10/2026, amostra aprovada por Eduardo): a explicação dos três níveis,
 * com o texto que ele escreveu. Abre e fecha com clique (o texto é longo e o CRM também é usado no celular) e fecha com
 * Esc sem fechar o painel. O nível escolhido vem primeiro, em destaque e com a palavra "Escolhido" (PAD-002: estado
 * nunca só por cor). O texto mora só aqui: mudou a definição, muda aqui. Sem siglas (pedido de Eduardo em 21/10/2026):
 * parceiro aparece pelo nome, nunca pela abreviação. */

import { useEffect } from "react";

export const NIVEIS_EXPLICADOS: Record<string, [string, string][]> = {
  Indicador: [
    ["O que é", "quem indica de vez em quando, sem rotina combinada. Pode ser pessoa física ou empresa."],
    ["Como funciona", "contrato padrão de indicação com finder fee (o primeiro foi assinado com a empresa do Gustavo). Recebe a 1ª parcela líquida nos contratos recorrentes e 10% do recebido nos não recorrentes, com vínculo de 12 meses."],
    ["O que a Critério oferece", "retorno sobre cada indicação. O relatório mensal fica disponível, mas não é obrigatório."],
    ["Follow-up sugerido", "a cada 6 meses."],
    ["Exemplo possível", "Gaidão."],
  ],
  Estruturado: [
    ["O que é", "parceiro que indica com frequência e com quem se combina um perfil de cliente (porte, setor, o que fica fora)."],
    ["Como funciona", "mesmo finder fee, mais rotina. Pedido de indicação a cada trimestre (como no roteiro de abordagem), relatório mensal das indicações e sócio responsável nomeado."],
    ["O que se espera", "indicações dentro do perfil combinado."],
    ["Follow-up sugerido", "a cada 3 meses."],
    ["Exemplo possível", "Molina, pelo histórico de contas trazidas."],
  ],
  "Estratégico": [
    ["O que é", "parceria de co-entrega. Os dois atendem o mesmo cliente, cada um na sua parte."],
    ["Como funciona", "divisão de escopo por escrito (no lugar da não concorrência de 24 meses do contrato padrão), indicação nos dois sentidos, eventos conjuntos e meta de piloto."],
    ["Follow-up sugerido", "todo mês."],
    ["Exemplo", "a Ficus. O jurídico tributário fica com a Ficus, e a Critério cuida da contabilidade, do fiscal e da operação da reforma, com o piloto de 20 clientes."],
  ],
};

export function BotaoInfoDosNiveis({ aberto, aoAlternar }: { aberto: boolean; aoAlternar: () => void }) {
  return (
    <button type="button" className={`botao-info${aberto ? " botao-info-aberto" : ""}`} onClick={aoAlternar}
      aria-label="O que é cada nível" aria-expanded={aberto} aria-controls="info-dos-niveis">
      i
    </button>
  );
}

export function InfoDosNiveis({ nivel, aoFechar }: { nivel: string; aoFechar: () => void }) {
  useEffect(() => {
    // Na captura, antes do painel lateral: o Esc fecha só a explicação.
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key !== "Escape") return;
      evento.stopPropagation();
      aoFechar();
    };
    window.addEventListener("keydown", aoTeclar, true);
    return () => window.removeEventListener("keydown", aoTeclar, true);
  }, [aoFechar]);

  const ordem = [nivel, ...Object.keys(NIVEIS_EXPLICADOS).filter((n) => n !== nivel)].filter((n) => NIVEIS_EXPLICADOS[n]);
  return (
    <div id="info-dos-niveis" className="info-dos-niveis" role="dialog" aria-label="Os níveis de parceiro">
      <div className="indicacao-topo">
        <strong>Os níveis de parceiro</strong>
        <button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>
      </div>
      {ordem.map((n) => (
        <section key={n} className={`info-do-nivel${n === nivel ? " info-do-nivel-escolhido" : ""}`} aria-label={n}>
          <div className="indicacao-topo">
            <strong>{n}</strong>
            {n === nivel && <span className="etiqueta etiqueta-andamento">Escolhido</span>}
          </div>
          <ul>
            {NIVEIS_EXPLICADOS[n].map(([titulo, texto]) => (
              <li key={titulo}><span className="info-do-nivel-titulo">{titulo}:</span> {texto}</li>
            ))}
          </ul>
        </section>
      ))}
      <p className="campo-ajuda">Níveis aprovados em 19/10/2026. Cadência de follow-up e exemplos são hipótese em validação.</p>
    </div>
  );
}

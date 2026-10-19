/** O relatório mensal ao parceiro (19/10/2026): uma página por parceiro, só a etapa, sem dado financeiro do cliente. */

import { describe, expect, it } from "vitest";
import type { RelatorioDoParceiro } from "./api/tipos";
import { htmlDosRelatorios, mesPadrao, nomeDoMes } from "./relatorioDoParceiro";

const REL: RelatorioDoParceiro = {
  parceiro_id: 1, parceiro: "Escritório <Alfa>", contato: "fernando@exemplo.com", mes: "2026-10", emitido_em: "2026-11-02",
  responsavel: "Eduardo", indicacoes: 2, novas_no_mes: 1, viraram_cliente: 1, fee_pago_no_mes: "13500.00",
  linhas: [
    { empresa: "Grupo Exemplo 6", indicada_em: "2026-10-14", etapa: "Em validação", proximo_passo: "Confirmação até 21/10/2026", servico_contratado: null },
    { empresa: "Grupo Exemplo 1", indicada_em: "2026-03-02", etapa: "Cliente", proximo_passo: null, servico_contratado: "BPO contábil" },
  ],
  fees: [{ empresa: "Grupo Exemplo 1", competencia: "2026-06-01", valor: "13500.00", situacao: "Pago em 20/10/2026" }],
};

describe("relatório mensal ao parceiro", () => {
  it("monta a página com etapa, próximo passo e fee, e escapa o texto", () => {
    const html = htmlDosRelatorios([REL]);
    expect(html).toContain("Suas indicações · outubro de 2026");
    expect(html).toContain("Escritório &lt;Alfa&gt;");
    expect(html).toContain("Confirmação até 21/10/2026");
    expect(html).toContain("BPO contábil");
    expect(html).toContain("Pago em 20/10/2026");
    expect(html).toContain('<div class="marca">Critério</div>');
  });

  it("uma página por parceiro", () => {
    const html = htmlDosRelatorios([REL, { ...REL, parceiro_id: 2, parceiro: "Molina", fees: [] }]);
    expect(html.match(/<section class="pagina">/g)).toHaveLength(2);
    expect(html.match(/Seus fees/g)).toHaveLength(1);
  });

  it("o mês padrão é o que acabou de fechar", () => {
    expect(mesPadrao(new Date(2026, 0, 5))).toBe("2025-12");
    expect(mesPadrao(new Date(2026, 9, 19))).toBe("2026-09");
    expect(nomeDoMes("2026-03")).toBe("março de 2026");
  });
});

/** O relatório mensal ao parceiro (19/10/2026, amostra aprovada por Eduardo): uma página por parceiro, aberta numa
 * janela própria pronta para "Salvar como PDF" na impressão do navegador. Sem biblioteca de PDF no servidor.
 *
 * O que entra: a etapa de cada indicação como o parceiro lê, a data do próximo contato (nunca o texto interno) e os
 * fees dele. O que não entra: nenhum dado financeiro do cliente indicado. A logomarca da Critério aparece sozinha. */

import type { RelatorioDoParceiro } from "./api/tipos";
import { data, dinheiro } from "./formato";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
  "novembro", "dezembro"];

export function nomeDoMes(mes: string): string {
  const [ano, m] = mes.split("-").map(Number);
  return `${MESES[m - 1]} de ${ano}`;
}

/** O mês anterior ao de hoje, em AAAA-MM: o relatório sai no começo do mês sobre o mês que fechou. */
export function mesPadrao(hoje = new Date()): string {
  const d = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const esc = (t: string | null | undefined) =>
  (t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function tom(etapa: string): string {
  if (etapa === "Cliente" || etapa.startsWith("Pago")) return "ganho";
  if (etapa === "Não seguiu" || etapa.startsWith("Não aceita")) return "perda";
  if (etapa === "Em validação" || etapa === "Em espera" || etapa === "Em aprovação") return "espera";
  return "andamento";
}

function pagina(r: RelatorioDoParceiro): string {
  const linhas = r.linhas.map((l) => `<tr><td>${esc(l.empresa)}</td><td>${data(l.indicada_em)}</td>
    <td><span class="et ${tom(l.etapa)}">${esc(l.etapa)}</span></td><td>${esc(l.proximo_passo) || "—"}</td>
    <td>${esc(l.servico_contratado) || "—"}</td></tr>`).join("");
  const fees = r.fees.map((f) => `<tr><td>${esc(f.empresa)}</td><td>${data(f.competencia).slice(3)}</td>
    <td class="n">${dinheiro(f.valor)}</td><td><span class="et ${tom(f.situacao)}">${esc(f.situacao)}</span></td></tr>`).join("");
  return `<section class="pagina">
    <div class="marca">Critério</div>
    <div class="topo"><div><h1>Suas indicações · ${nomeDoMes(r.mes)}</h1>
      <p>Para: ${esc(r.parceiro)}${r.contato ? ` · ${esc(r.contato)}` : ""}</p></div>
      <p>Emitido em ${data(r.emitido_em)}${r.responsavel ? ` · responsável: ${esc(r.responsavel)}` : ""}</p></div>
    <div class="cards">
      <div><span>Indicações desde o início</span><b>${r.indicacoes}</b></div>
      <div><span>Novas no mês</span><b>${r.novas_no_mes}</b></div>
      <div><span>Viraram cliente</span><b>${r.viraram_cliente}</b></div>
      <div><span>Fee pago no mês</span><b>${dinheiro(r.fee_pago_no_mes)}</b></div>
    </div>
    <table><thead><tr><th>Empresa indicada</th><th>Indicada em</th><th>Etapa</th><th>Próximo passo</th><th>Serviço contratado</th></tr></thead>
      <tbody>${linhas || `<tr><td colspan="5">Nenhuma indicação até o fim do mês.</td></tr>`}</tbody></table>
    ${r.fees.length ? `<h2>Seus fees</h2><table><thead><tr><th>Empresa</th><th>Competência</th><th class="n">Valor</th><th>Situação</th></tr></thead>
      <tbody>${fees}</tbody></table>` : ""}
    <p class="rodape">Vínculo de cada indicação: 12 meses a partir da validação (cláusula 2.3). Este relatório não traz dado
      financeiro do cliente indicado, só a etapa.</p>
  </section>`;
}

export function htmlDosRelatorios(relatorios: RelatorioDoParceiro[]): string {
  const titulo = relatorios.length === 1
    ? `Indicações ${relatorios[0].parceiro} ${relatorios[0].mes}`
    : `Indicações dos parceiros ${relatorios[0]?.mes ?? ""}`;
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(titulo)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500&family=Source+Serif+4:wght@600&display=swap" rel="stylesheet">
  <style>
    @page { size: A4; margin: 16mm; }
    body { font-family: Poppins, system-ui, sans-serif; color: #16202f; font-size: 11px; margin: 0; }
    .pagina { page-break-after: always; }
    .pagina:last-child { page-break-after: auto; }
    .marca { font-family: "Source Serif 4", Georgia, serif; font-size: 20px; font-weight: 600; color: #1a2338;
      padding-bottom: 8px; border-bottom: 1px solid #d5dbe3; margin-bottom: 14px; }
    .topo { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
    h1 { font-family: "Source Serif 4", Georgia, serif; font-size: 17px; margin: 0; }
    h2 { font-size: 12px; margin: 16px 0 6px; }
    p { margin: 2px 0; color: #4a5568; }
    .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 14px 0; }
    .cards div { background: #f4f6f9; border-radius: 6px; padding: 8px 10px; }
    .cards span { display: block; color: #4a5568; font-size: 10px; }
    .cards b { font-size: 16px; font-weight: 500; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 6px 4px; border-bottom: 1px solid #d5dbe3; vertical-align: top; }
    th { color: #4a5568; font-weight: 500; font-size: 10px; }
    .n { text-align: right; }
    .et { padding: 1px 7px; border-radius: 6px; font-size: 10px; white-space: nowrap; }
    .ganho { background: #e4f3ea; color: #1d6f47; } .perda { background: #fbeaea; color: #9b2c2c; }
    .espera { background: #fdf3e2; color: #8a5a12; } .andamento { background: #e6eff8; color: #21528a; }
    .rodape { margin-top: 14px; font-size: 10px; }
  </style></head><body>${relatorios.map(pagina).join("")}</body></html>`;
}

/** Imprime por um quadro invisível na própria página, sem abrir janela nova: o navegador não bloqueia, e no diálogo de
 * impressão se escolhe "Salvar como PDF". O quadro sai depois da impressão. */
export function abrirParaImprimir(relatorios: RelatorioDoParceiro[]): boolean {
  const quadro = document.createElement("iframe");
  quadro.setAttribute("aria-hidden", "true");
  quadro.title = "Relatório para imprimir";
  Object.assign(quadro.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0" });
  document.body.appendChild(quadro);
  const doc = quadro.contentDocument;
  const janela = quadro.contentWindow;
  if (!doc || !janela) {
    quadro.remove();
    return false;
  }
  doc.open();
  doc.write(htmlDosRelatorios(relatorios));
  doc.close();
  // A fonte carrega depois do write: espera o load, com um teto para o navegador que não dispara o evento.
  let impresso = false;
  const imprimir = () => {
    if (impresso) return;
    impresso = true;
    janela.focus();
    janela.print();
    setTimeout(() => quadro.remove(), 60_000);
  };
  quadro.onload = imprimir;
  setTimeout(imprimir, 1200);
  return true;
}

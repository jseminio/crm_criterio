// Exemplo mínimo no template da Critério: um slide de cada layout, com texto de demonstração.
// Uso: npm install && node exemplo.js saida/exemplo.pptx
// As cores do tema só ficam certas depois do applyTheme da skill pptx; sem ela, o texto usa
// as cores fixas dos layouts e os fundos do template, mas as cores de esquema caem no padrão do Office.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { THEME, COR, X0, W, HEAD, definirLayouts, helpers } = require("./estilo-template");

const OUT = process.argv[2] || "saida/exemplo.pptx";
fs.mkdirSync(path.dirname(OUT), { recursive: true });

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13,333" × 7,5", o mesmo do template
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Exemplo no template da Critério";
const C = pres.SchemeColor;
definirLayouts(pres);
const { txt, regua, reguaV, ponto, cab, destaque, forte, dir, tabela } = helpers(pres);

pres.addSection({ title: "Exemplo" });
{
  const s = pres.addSlide({ masterName: "CAPA", sectionTitle: "Exemplo" });
  s.addText("EYEBROW · MÊS DE ANO", { placeholder: "eyebrow" });
  s.addText("Título da apresentação", { placeholder: "title" });
  s.addText("Subtítulo com a mensagem principal.", { placeholder: "subtitle" });
  s.addText("Autor · Área", { placeholder: "author" });
}
{
  // Números grandes em azul-claro com réguas finas, sobre o fundo preto.
  const s = pres.addSlide({ masterName: "ESCURO", sectionTitle: "Exemplo" });
  s.addText("Título em coluna estreita, à esquerda", { placeholder: "title" });
  const xR = 6.6, wR = 12.87 - xR;
  [["Rótulo", "detalhe", "123", "Descrição curta do número"], ["Rótulo", "detalhe", "45%", "Descrição curta do número"]].forEach(([rot, sub, num, desc], i) => {
    const y = 0.5 + i * 1.95;
    txt(s, `rotulo-${i}`, [{ text: rot, options: { fontSize: 20, color: C.background1, breakLine: true } }, { text: sub, options: { fontSize: 12, color: C.accent5 } }], { x: xR, y: y + 0.2, w: 1.9, h: 0.9 });
    txt(s, `numero-${i}`, num, { x: xR + 2.05, y, w: wR - 2.05, h: 1.0, fontFace: HEAD, fontSize: 48, color: C.accent6, valign: "middle" });
    txt(s, `desc-${i}`, desc, { x: xR + 2.05, y: y + 1.05, w: wR - 2.05, h: 0.55, fontSize: 14, color: C.background1 });
    regua(s, `regua-${i}`, xR, y + 1.75, wR, "5A6779");
  });
}
{
  // Linha do tempo com pontos e tabela de cabeçalho navy, sobre o fundo branco.
  const s = pres.addSlide({ masterName: "CONTEUDO", sectionTitle: "Exemplo" });
  s.addText("Título do slide de conteúdo", { placeholder: "title" });
  const gap = 0.4, cw = (W - 2 * gap) / 3, yLinha = 1.95;
  regua(s, "linha-tempo", X0, yLinha, W, C.text2, 1);
  ["Etapa 1", "Etapa 2", "Etapa 3"].forEach((t, i) => {
    const x = X0 + i * (cw + gap);
    ponto(s, `ponto-${i}`, x + 0.11, yLinha, 0.22, C.text2);
    txt(s, `etapa-${i}`, t, { x, y: 2.2, w: cw, h: 0.55, fontFace: HEAD, fontSize: 24, color: C.text1 });
  });
  tabela(s, [
    [cab("Coluna"), cab("Valor", "right")],
    [forte("Linha"), dir("10")],
    [destaque("Total"), destaque("10", "right")],
  ], { x: X0, y: 3.3, w: 7, colW: [5, 2], fontSize: 15, rowH: 0.5, objectName: "tabela" });
  txt(s, "nota", "Nota de rodapé do slide, em cinza.", { x: X0, y: 6.3, w: W, h: 0.35, fontSize: 13, color: COR.MUTED });
}
{
  const s = pres.addSlide({ masterName: "COLUNA", sectionTitle: "Exemplo" });
  s.addText("Título à esquerda, gráfico à direita", { placeholder: "title" });
  reguaV(s, "divisoria", 5.85, 0.6, 5.6);
  s.addChart(pres.charts.BAR, [{ name: "Série", labels: ["A", "B", "C"], values: [3, 5, 4] }], {
    x: 6.1, y: 0.5, w: 6.77, h: 5.75, barDir: "col", chartColors: ["1A2338"], showValue: true, dataLabelFontFace: "+mn-lt",
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", showLegend: false, valGridLine: { color: "E4EAF1", size: 0.5 }, catGridLine: { style: "none" },
  });
}
{
  const s = pres.addSlide({ masterName: "DIVISOR_1", sectionTitle: "Exemplo" });
  s.addText("SEÇÃO", { placeholder: "eyebrow" });
  s.addText("Título do divisor", { placeholder: "title" });
}
pres.addSlide({ masterName: "OBRIGADO", sectionTitle: "Exemplo" });

(async () => {
  await pres.writeFile({ fileName: OUT });
  const skill = process.env.PPTX_SKILL_DIR;
  if (skill) {
    const { applyTheme } = require(path.join(skill, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } else {
    console.log("Aviso: PPTX_SKILL_DIR não definido; cores do tema não aplicadas.");
  }
  console.log("ok", OUT);
})();

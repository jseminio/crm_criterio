// Estilo do template da Critério (template-criterio.pptx): fundos em imagem com rodapé e logomarca,
// fonte Delight, títulos à esquerda, réguas finas e números grandes em azul-claro.
// Uso: definirLayouts(pres) cria os layouts; helpers(pres) devolve as funções de desenho. Ver README.md.
const path = require("path");

const FUNDOS = path.join(__dirname, "fundos");
const fundo = (nome) => ({ path: path.join(FUNDOS, nome) });

const THEME = {
  name: "Critério",
  headFontFace: "Delight SemBd",
  bodyFontFace: "Delight Regular",
  colors: {
    dk1: "0B0E17", lt1: "FFFFFF", dk2: "1A2338", lt2: "F4F7FA",
    accent1: "0072B2", accent2: "D55E00", accent3: "0F6B52", accent4: "8A5300",
    accent5: "A5C0D6", accent6: "CAE3F7", hlink: "17497A", folHlink: "5A6779",
  },
};

// Neutros e estados do sistema de design que não cabem nos 12 papéis do tema.
const COR = {
  INK: "2A3242", MUTED: "5A6779", BORDER: "DBE3EC", SUNKEN: "E8EEF5", LABEL: "17497A",
  MSG_BG: "E4EEF8", ATENCAO_SUAVE: "FBEFDC", GANHO_SUAVE: "E2F3ED", IA_SUAVE: "EFE9FA", IA_INK: "3F2C6B",
};

// Grade do template: o rodapé começa em 0,47" e termina em 12,90"; a linha do rodapé fica em 6,93".
const X0 = 0.47, W = 12.4, Y_TITULO = 0.44, Y_MAX = 6.72;

const HEAD = "+mj-lt"; // Delight SemBd, pelo tema

function definirLayouts(pres, { comEyebrow = false } = {}) {
  const C = pres.SchemeColor;
  const numero = (cor) => ({ x: 9.95, y: 7.0, w: 0.57, h: 0.4, fontFace: "Delight Regular", fontSize: 12, color: cor, align: "center", valign: "middle" });
  const eyebrow = (cor) => ({ placeholder: { options: { name: "eyebrow", type: "body", x: X0, y: 0.3, w: W, h: 0.3, fontSize: 12, color: cor, charSpacing: 2, margin: 0 }, text: "" } });
  const yT = comEyebrow ? 0.62 : Y_TITULO;

  pres.defineSlideMaster({
    title: "CAPA",
    background: fundo("gradiente-luz.jpg"),
    objects: [
      { placeholder: { options: { name: "eyebrow", type: "body", x: X0, y: 2.45, w: W, h: 0.4, fontSize: 14, color: C.accent6, charSpacing: 3, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", align: "left", x: X0, y: 2.95, w: W, h: 2.0, fontSize: 48, color: C.background1, valign: "top", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "subtitle", type: "body", x: X0, y: 5.0, w: 10.5, h: 0.8, fontSize: 18, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "author", type: "body", x: X0, y: 6.15, w: 9, h: 0.35, fontSize: 14, color: C.accent5, margin: 0 }, text: "" } },
    ],
  });

  const conteudo = (title, bg, corTitulo, corNumero, corEyebrow, wTitulo, hTitulo) => pres.defineSlideMaster({
    title,
    background: fundo(bg),
    objects: [
      ...(comEyebrow ? [eyebrow(corEyebrow)] : []),
      { placeholder: { options: { name: "title", type: "title", align: "left", x: X0, y: yT, w: wTitulo, h: hTitulo, fontSize: 32, color: corTitulo, valign: "top", margin: 0 }, text: "" } },
    ],
    slideNumber: numero(corNumero),
  });
  conteudo("CONTEUDO", "branco.png", C.text1, C.text1, COR.MUTED, W, 0.8);
  conteudo("COLUNA", "branco.png", C.text1, C.text1, COR.MUTED, 5.0, 1.5);
  conteudo("ESCURO", "preto.png", C.background1, C.background1, C.accent5, 5.0, 2.3);
  conteudo("NAVY", "navy.png", C.background1, C.background1, C.accent5, W, 0.8);

  // Divisores de seção sobre os fundos fotográficos do template.
  ["gradiente-azul.jpg", "blocos-escuros.jpg", "blocos-azuis.jpg", "nevoa.jpg", "gradiente-luz.jpg"].forEach((bg, i) => {
    pres.defineSlideMaster({
      title: `DIVISOR_${i + 1}`,
      background: fundo(bg),
      objects: [
        { placeholder: { options: { name: "eyebrow", type: "body", x: X0, y: 0.6, w: W, h: 0.4, fontSize: 14, color: C.accent6, charSpacing: 3, margin: 0 }, text: "" } },
        { placeholder: { options: { name: "title", type: "title", align: "left", x: X0, y: 1.05, w: W, h: 1.0, fontSize: 48, color: C.background1, valign: "top", margin: 0 }, text: "" } },
      ],
      slideNumber: numero(C.background1),
    });
  });

  // Encerramento do template ("Obrigado!"), com o texto e o contato da própria Critério.
  pres.defineSlideMaster({
    title: "OBRIGADO",
    background: fundo("blocos-azuis.jpg"),
    objects: [
      { text: { text: "Obrigado!", options: { x: X0, y: 0.45, w: 6, h: 1.0, fontFace: HEAD, fontSize: 54, color: C.background1, margin: 0, valign: "top" } } },
      { text: { text: "Conduzindo negócios e fortalecendo empresas que liderarão o futuro.", options: { x: 9.13, y: 0.5, w: 3.77, h: 1.8, fontFace: HEAD, fontSize: 24, color: C.background1, margin: 0, valign: "top" } } },
      { text: { text: "Rua do Rosário, 103 - 12° Andar\nCentro, Rio de Janeiro - RJ, 20041-004\n\nTelefone: (21) 2233-0977\nWhatsapp: (21) 9 9439-1156\n\ncontato@grupocriterio.com.br", options: { x: 9.13, y: 4.3, w: 3.77, h: 2.2, fontFace: "Delight Light", fontSize: 14, color: C.background1, margin: 0, valign: "top" } } },
    ],
  });
}

function helpers(pres) {
  const C = pres.SchemeColor;
  const txt = (s, name, text, opts) => s.addText(text, { isTextBox: true, margin: 0, color: COR.INK, fontSize: 16, valign: "top", objectName: name, ...opts });
  // Painel liso, sem borda arredondada nem sombra: o template não usa cartões.
  const painel = (s, name, x, y, w, h, fill) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, objectName: name });
  const regua = (s, name, x, y, w, cor = COR.BORDER, pt = 0.75) => s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: cor, width: pt }, objectName: name });
  const reguaV = (s, name, x, y, h, cor = COR.BORDER, pt = 0.75) => s.addShape(pres.shapes.LINE, { x, y, w: 0, h, line: { color: cor, width: pt }, objectName: name });
  const ponto = (s, name, x, y, d, cor) => s.addShape(pres.shapes.OVAL, { x: x - d / 2, y: y - d / 2, w: d, h: d, fill: { color: cor }, line: { type: "none" }, objectName: name });

  // Tabelas no estilo do template: cabeçalho navy, só réguas horizontais.
  const LINHA = { type: "solid", pt: 0.75, color: COR.BORDER };
  const SEM = { type: "none" };
  const bordas = [LINHA, SEM, LINHA, SEM];
  const cab = (t, align) => ({ text: t, options: { fontFace: HEAD, fill: { color: C.text2 }, color: C.background1, align, border: bordas } });
  const destaque = (t, align) => ({ text: t, options: { fontFace: HEAD, fill: { color: C.accent6 }, color: C.text1, align, border: bordas } });
  const forte = (t) => ({ text: t, options: { fontFace: HEAD, color: C.text1 } });
  const dir = (t) => ({ text: t, options: { align: "right" } });
  const tabela = (s, linhas, opts) => s.addTable(linhas, { fontFace: "Delight Regular", color: COR.INK, border: bordas, valign: "middle", ...opts });

  return { txt, painel, regua, reguaV, ponto, cab, destaque, forte, dir, tabela };
}

module.exports = { THEME, COR, X0, W, Y_TITULO, Y_MAX, HEAD, definirLayouts, helpers };

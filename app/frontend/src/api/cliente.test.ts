/** O acesso à API — onde a distinção entre "servidor fora do ar" e "servidor
 * recusou" nasce, e de onde toda tela puxa a mensagem de erro que mostra. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "./cliente";

function respostaJson(corpo: unknown, status = 200) {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("devolve o corpo já decodificado numa chamada com sucesso", async () => {
    vi.mocked(fetch).mockResolvedValue(respostaJson({ situacoes: ["Aceita"] }));

    const listas = await api.listas();

    expect(listas).toEqual({ situacoes: ["Aceita"] });
  });

  it("chama a rota certa com o método certo", async () => {
    vi.mocked(fetch).mockResolvedValue(respostaJson({}));

    await api.listas();

    const [url, opcoes] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/listas");
    expect(opcoes?.method).toBeUndefined(); // GET é o padrão do fetch
  });

  it("usa PATCH para editar oportunidade, com o corpo em JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(respostaJson({ id: 1 }));

    await api.editarOportunidade(1, { situacao: "Aceita" });

    const [url, opcoes] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/oportunidades/1");
    expect(opcoes?.method).toBe("PATCH");
    expect(opcoes?.body).toBe(JSON.stringify({ situacao: "Aceita" }));
  });

  it("distingue servidor fora do ar (status 0) de servidor que recusou", async () => {
    // A diferença importa: a primeira se resolve subindo a API — como no
    // iniciar.sh —, a segunda não. Confundir as duas manda a pessoa procurar
    // o problema no lugar errado.
    vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.listas()).rejects.toMatchObject({
      status: 0,
      message: expect.stringMatching(/servidor.*no ar/i),
    });
  });

  it("uma resposta de erro com detail vira a mensagem do ErroDaApi", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respostaJson({ detail: "para marcar como aceita, informe a data do aceite" }, 422),
    );

    await expect(api.editarOportunidade(1, { situacao: "Aceita" })).rejects.toMatchObject({
      status: 422,
      message: "para marcar como aceita, informe a data do aceite",
    });
  });

  it("recusa da validação (detail em lista) diz o campo e o motivo, em vez de só o código", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respostaJson({
        detail: [
          { loc: ["body", "contextualizacao"], type: "string_type", msg: "Input should be a valid string" },
          { loc: ["body", "valor_contabil"], type: "decimal_max_places", msg: "x", ctx: { decimal_places: 2 } },
          { loc: ["body", "campo_novo"], type: "algo", msg: "Mensagem do servidor" },
        ],
      }, 422),
    );

    await expect(api.listas()).rejects.toMatchObject({
      status: 422,
      message:
        "Contextualização: não pode ficar em branco; Honorário Contábil/Fiscal: use no máximo 2 casas decimais; " +
        "campo_novo: Mensagem do servidor",
    });
  });

  it("um erro sem corpo em JSON ainda vira ErroDaApi, com mensagem genérica", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("erro interno do servidor", { status: 500 }),
    );

    await expect(api.listas()).rejects.toMatchObject({ status: 500, message: "Erro 500" });
  });

  it("é de fato um ErroDaApi, não um Error qualquer — quem chama depende disso", async () => {
    vi.mocked(fetch).mockResolvedValue(respostaJson({ detail: "recusado" }, 409));

    await expect(api.listas()).rejects.toBeInstanceOf(ErroDaApi);
  });

  it("monta os parâmetros de busca só com o que tem valor", async () => {
    vi.mocked(fetch).mockResolvedValue(respostaJson({ total: 0, itens: [] }));

    await api.oportunidades({ busca: "Aeskins", captador: undefined, situacao: ["Aceita"] });

    const [url] = vi.mocked(fetch).mock.calls[0];
    const parametros = new URLSearchParams((url as string).split("?")[1]);
    expect(parametros.get("busca")).toBe("Aeskins");
    expect(parametros.has("captador")).toBe(false);
    expect(parametros.getAll("situacao")).toEqual(["Aceita"]);
  });

  it("não vaza status 204 (sem corpo) como tentativa de ler JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    await expect(api.editarLead(1, {})).resolves.toBeUndefined();
  });
});

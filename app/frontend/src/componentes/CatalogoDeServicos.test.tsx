/** O pop-up do catálogo de serviços (27/09/2026). */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { ServicoDoCatalogo } from "../api/tipos";
import { EscolhaDeServico } from "./CatalogoDeServicos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { servicos: vi.fn() } };
});

const CATALOGO: ServicoDoCatalogo[] = [
  {
    nome: "Dep. Pessoal", nome_por_extenso: null, linha: "C1", recorrente: true,
    para_quem: "Empresa que quer terceirizar só a folha.",
    perguntas: [{ texto: "Empregados CLT", direcionador: "empregados_clt" }, { texto: "Sindicato", direcionador: null }],
    fora_do_perfil: ["Nenhum empregado CLT"], transbordo: "Comercial · BPO (C1)", nomes_antigos: [], rascunho: true, temas: [],
  },
  {
    nome: "Legalização Empresarial", nome_por_extenso: null, linha: "C2", recorrente: false,
    para_quem: "Abrir, alterar ou encerrar empresa.", perguntas: [{ texto: "UF e município", direcionador: null }],
    fora_do_perfil: [], transbordo: "Consultoria (C2)", nomes_antigos: ["Legalização"], rascunho: true, temas: [],
  },
  {
    nome: "FSCP", nome_por_extenso: "Finance Statement Closing Procedure", linha: "C2", recorrente: false,
    para_quem: "Fechamento das demonstrações.", perguntas: [], fora_do_perfil: [],
    transbordo: "Consultoria (C2)", nomes_antigos: [], rascunho: true, temas: [],
  },
];

function Formulario({
  inicial = "",
  aoEscolher = vi.fn(),
}: {
  inicial?: string;
  aoEscolher?: (n: string, d: string, t: string) => void;
}) {
  const [valor, definirValor] = useState(inicial);
  const [descricao, definirDescricao] = useState("");
  const [tema, definirTema] = useState("");
  return (
    <EscolhaDeServico
      id="t-servico"
      rotulo="Serviço"
      valor={valor}
      descricao={descricao}
      tema={tema}
      aoEscolher={(n, d, t) => {
        definirValor(n);
        definirDescricao(d);
        definirTema(t);
        aoEscolher(n, d, t);
      }}
    />
  );
}

async function abrir() {
  await userEvent.click(screen.getByRole("button", { name: /^Serviço/ }));
  return screen.findByRole("dialog", { name: "Catálogo de serviços" });
}

describe("catálogo de serviços", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.servicos).mockResolvedValue(CATALOGO);
  });

  it("agrupa em C1 recorrente e C2 não recorrente", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    expect(within(dialogo).getByRole("listbox", { name: "C1 · Recorrente" })).toHaveTextContent("Dep. Pessoal");
    expect(within(dialogo).getByRole("listbox", { name: "C2 · Não recorrente" })).toHaveTextContent("FSCP");
  });

  it("mostra o roteiro do serviço escolhido, sem preço", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    await userEvent.click(within(dialogo).getByRole("option", { name: "Dep. Pessoal" }));

    expect(within(dialogo).getByText("Empregados CLT")).toBeInTheDocument();
    expect(within(dialogo).getByText("régua de porte")).toBeInTheDocument();
    expect(within(dialogo).getByText("Nenhum empregado CLT")).toBeInTheDocument();
    expect(within(dialogo).getByText("texto em rascunho")).toBeInTheDocument();
    expect(within(dialogo).getByText(/Sem preço/)).toBeInTheDocument();
    expect(within(dialogo).queryByText(/R\$/)).not.toBeInTheDocument();
  });

  it("usar este serviço preenche o campo com o nome e a linha", async () => {
    const aoEscolher = vi.fn();
    render(<Formulario aoEscolher={aoEscolher} />);
    const dialogo = await abrir();

    await userEvent.click(within(dialogo).getByRole("option", { name: "FSCP" }));
    expect(within(dialogo).getByText("Finance Statement Closing Procedure")).toBeInTheDocument();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Usar este serviço" }));

    expect(aoEscolher).toHaveBeenCalledWith("FSCP", "", "");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Serviço FSCP C2 · Não recorrente/ })).toBeInTheDocument();
  });

  it("a busca acha pelo nome antigo e ignora acento", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    await userEvent.type(within(dialogo).getByLabelText("Buscar serviço"), "legalizacao");

    // "Outro serviço" fica sempre no fim, para o que não estiver na lista.
    expect(within(dialogo).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Legalização Empresarial",
      "Outro serviço",
    ]);
  });

  it("busca sem resultado oferece limpar", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    await userEvent.type(within(dialogo).getByLabelText("Buscar serviço"), "xyz");

    expect(within(dialogo).getByText(/Nenhum serviço com esse nome/)).toBeInTheDocument();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Limpar a busca" }));
    expect(within(dialogo).getAllByRole("option")).toHaveLength(4);
  });

  it("Esc fecha sem escolher", async () => {
    const aoEscolher = vi.fn();
    render(<Formulario aoEscolher={aoEscolher} />);
    await abrir();

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(aoEscolher).not.toHaveBeenCalled();
  });

  it("valor antigo fora do catálogo aparece marcado", async () => {
    render(<Formulario inicial="Serviço de 2019" />);

    expect(await screen.findByText("fora do catálogo")).toBeInTheDocument();
  });

  it("erro ao carregar tem tentar de novo", async () => {
    vi.mocked(api.servicos).mockRejectedValue(new ErroDaApi(0, "Não consegui falar com o servidor."));
    render(<Formulario />);
    const dialogo = await abrir();

    expect(await within(dialogo).findByText("Não consegui falar com o servidor.")).toBeInTheDocument();
    expect(within(dialogo).getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("uma ação primária no pop-up", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    expect(dialogo.querySelectorAll(".botao-primario")).toHaveLength(1);
  });
});

describe("outro serviço", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.servicos).mockResolvedValue(CATALOGO);
  });

  it("pede a descrição e só libera com ao menos 10 caracteres", async () => {
    const aoEscolher = vi.fn();
    render(<Formulario aoEscolher={aoEscolher} />);
    const dialogo = await abrir();

    await userEvent.click(within(dialogo).getByRole("option", { name: "Outro serviço" }));
    const usar = within(dialogo).getByRole("button", { name: "Usar outro serviço" });
    expect(usar).toBeDisabled();
    expect(within(dialogo).getByText("Linha: ainda não sei")).toBeInTheDocument();

    await userEvent.type(within(dialogo).getByLabelText("Descreva o serviço desejado"), "Perícia contábil judicial");
    expect(usar).toBeEnabled();
    await userEvent.click(usar);

    expect(aoEscolher).toHaveBeenCalledWith("Outro", "Perícia contábil judicial", "");
    expect(screen.getByRole("button", { name: /^Serviço Outro: Perícia contábil judicial Linha: ainda não sei/ })).toBeInTheDocument();
  });

  it("aparece mesmo quando a busca não acha nada", async () => {
    render(<Formulario />);
    const dialogo = await abrir();

    await userEvent.type(within(dialogo).getByLabelText("Buscar serviço"), "pericia");

    expect(within(dialogo).getByText(/use "Outro serviço"/)).toBeInTheDocument();
    expect(within(dialogo).getByRole("option", { name: "Outro serviço" })).toBeInTheDocument();
  });
});


describe("tema da consultoria", () => {
  const COM_TEMAS: ServicoDoCatalogo[] = [
    {
      nome: "Consultoria", nome_por_extenso: null, linha: "C2", recorrente: false,
      para_quem: "Projeto com começo e fim.", perguntas: [{ texto: "Qual é o tema", direcionador: null }],
      fora_do_perfil: [], transbordo: "Consultoria (C2)", nomes_antigos: [], rascunho: true,
      temas: [
        { nome: "Tributária e fiscal", perguntas: [{ texto: "Regime tributário", direcionador: null }] },
        { nome: "Valuation, PPA e laudos", perguntas: [{ texto: "Data-base", direcionador: null }] },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.servicos).mockResolvedValue(COM_TEMAS);
  });

  it("só libera com o tema escolhido, e as perguntas seguem o tema", async () => {
    const aoEscolher = vi.fn();
    render(<Formulario aoEscolher={aoEscolher} />);
    const dialogo = await abrir();

    await userEvent.click(within(dialogo).getByRole("option", { name: "Consultoria" }));
    const usar = within(dialogo).getByRole("button", { name: "Usar este serviço" });
    expect(usar).toBeDisabled();
    expect(within(dialogo).getByText("Escolha o tema para continuar.")).toBeInTheDocument();

    await userEvent.click(within(dialogo).getByLabelText("Valuation, PPA e laudos"));
    expect(within(dialogo).getByText("Data-base")).toBeInTheDocument();
    expect(within(dialogo).queryByText("Regime tributário")).not.toBeInTheDocument();
    expect(usar).toBeEnabled();

    await userEvent.click(usar);
    expect(aoEscolher).toHaveBeenCalledWith("Consultoria", "", "Valuation, PPA e laudos");
    expect(
      screen.getByRole("button", { name: /^Serviço Consultoria · Valuation, PPA e laudos C2/ }),
    ).toBeInTheDocument();
  });

  it("proposta antiga de Consultoria sem tema mostra que falta o tema", async () => {
    render(<Formulario inicial="Consultoria" />);

    expect(await screen.findByText("falta o tema")).toBeInTheDocument();
  });
});

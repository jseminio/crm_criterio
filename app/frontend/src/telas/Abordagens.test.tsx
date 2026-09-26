/** A fila do agente SDR. O que mais importa: "Aprovar" só é a ação disponível
 * quando o texto está salvo e as conferências passaram — nada sai sem isso. */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { AbordagemDetalhe, AbordagemResumo, Pagina, ResumoDasAbordagens } from "../api/tipos";
import { Abordagens, mesPadrao, nomeDoMes } from "./Abordagens";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      abordagens: vi.fn(),
      abordagem: vi.fn(),
      resumoDasAbordagens: vi.fn(),
      editarAbordagem: vi.fn(),
      prepararAbordagem: vi.fn(),
      pedirOutraVersao: vi.fn(),
      aprovarAbordagem: vi.fn(),
      marcarAbordagemEnviada: vi.fn(),
      descartarAbordagem: vi.fn(),
    },
  };
});

const m = vi.mocked(api);

function resumo(extra: Partial<AbordagemResumo> = {}): AbordagemResumo {
  return {
    id: 1,
    grupo_id: 10,
    grupo_nome: "Conta Alfa",
    mes: "2026-10",
    quem_apresenta: "Parceiro A",
    canal: "E-mail",
    situacao: "Aguardando aprovação",
    proximo_passo: "Revisar o rascunho",
    atualizado_em: "2026-09-26T20:00:00Z",
    ...extra,
  };
}

function detalhe(extra: Partial<AbordagemDetalhe> = {}): AbordagemDetalhe {
  return {
    ...resumo(),
    contexto: null,
    destinatario: "ana@alfa.com.br",
    assunto: "Retomando a conversa",
    mensagem: "Olá, [nome]. Proponho 30 minutos.",
    versao: 1,
    erro: null,
    ficha: {
      historico: "Staff loan em espera desde fev/25.",
      pesquisa: [{ fato: "Abriu filial", fonte: "https://exemplo.com/f" }],
      quem_decide: "Diretora financeira",
      modelo: "claude-opus-5",
      criado_em: "2026-09-26T20:00:00Z",
    },
    conferencias: [
      { regra: "sem_preco", ok: true, texto: "Sem preço na mensagem" },
      { regra: "colchetes", ok: false, texto: "Há campos entre colchetes para preencher, como [nome]" },
    ],
    pode_aprovar: false,
    aprovada_por: null,
    aprovada_em: null,
    enviada_em: null,
    diagnostico_agendado_em: null,
    link_whatsapp: null,
    ...extra,
  };
}

const RESUMO: ResumoDasAbordagens = {
  mes: "2026-10",
  na_fila: 1,
  abordadas: 0,
  diagnosticos: 0,
  aguardando_aprovacao: 1,
  custo_usd: "0.6200",
  custo_parcial: false,
};

function pagina(itens: AbordagemResumo[]): Pagina<AbordagemResumo> {
  return { total: itens.length, itens };
}

async function abrirConta(nome = "Conta Alfa") {
  await userEvent.click(await screen.findByRole("button", { name: nome }));
  return screen.findByRole("complementary", { name: `${nome}: ficha e rascunho` });
}

beforeEach(() => {
  vi.clearAllMocks();
  m.resumoDasAbordagens.mockResolvedValue(RESUMO);
});

describe("Abordagens", () => {
  it("fila vazia explica como as contas entram", async () => {
    m.abordagens.mockResolvedValue(pagina([]));
    render(<Abordagens />);
    expect(await screen.findByText("Nenhuma conta na fila")).toBeInTheDocument();
    expect(screen.getByText(/importar_abordagens\.py/)).toBeInTheDocument();
  });

  it("erro ao carregar oferece tentar de novo", async () => {
    m.abordagens.mockRejectedValueOnce(new ErroDaApi(0, "Não consegui falar com o servidor."));
    m.abordagens.mockResolvedValueOnce(pagina([resumo()]));
    render(<Abordagens />);
    expect(await screen.findByText("Não consegui falar com o servidor.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("button", { name: "Conta Alfa" })).toBeInTheDocument();
  });

  it("filtro sem resultado é diferente de fila vazia", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo()]));
    render(<Abordagens />);
    await screen.findByRole("button", { name: "Conta Alfa" });
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Enviada");
    expect(screen.getByText("Nenhum resultado para esses filtros")).toBeInTheDocument();
  });

  it("mostra situação com palavra e o custo estimado", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo({ situacao: "Bloqueada", quem_apresenta: null })]));
    render(<Abordagens />);
    const tabela = await screen.findByRole("table");
    expect(within(tabela).getByText("Bloqueada")).toHaveClass("etiqueta");
    expect(within(tabela).getByText("A confirmar")).toBeInTheDocument();
    expect(await screen.findByText("US$ 0,62")).toBeInTheDocument();
  });

  it("com conferência pendente, aprovar fica desligado e diz por quê", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo()]));
    m.abordagem.mockResolvedValue(detalhe());
    render(<Abordagens />);
    const painel = await abrirConta();
    const aprovar = within(painel).getByRole("button", { name: "Aprovar e enviar por e-mail" });
    expect(aprovar).toBeDisabled();
    expect(within(painel).getByText("Atenção")).toBeInTheDocument();
    expect(within(painel).getByText(/campos entre colchetes/)).toBeInTheDocument();
    // Uma ação primária por painel (PAD-002).
    expect(painel.querySelectorAll(".botao-primario")).toHaveLength(1);
  });

  it("texto alterado precisa ser salvo antes de aprovar", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo()]));
    m.abordagem.mockResolvedValue(detalhe({ pode_aprovar: true, conferencias: [] }));
    m.editarAbordagem.mockResolvedValue(detalhe());
    render(<Abordagens />);
    const painel = await abrirConta();
    const aprovar = within(painel).getByRole("button", { name: "Aprovar e enviar por e-mail" });
    expect(aprovar).toBeEnabled();

    const mensagem = within(painel).getByLabelText("Mensagem");
    await userEvent.clear(mensagem);
    await userEvent.type(mensagem, "Olá, Ana.");
    expect(aprovar).toBeDisabled();
    expect(within(painel).getByText(/Salve as alterações antes de aprovar/)).toBeInTheDocument();

    await userEvent.click(within(painel).getByRole("button", { name: "Salvar alterações" }));
    await waitFor(() =>
      expect(m.editarAbordagem).toHaveBeenCalledWith(1, { mensagem: "Olá, Ana." }),
    );
  });

  it("aprovar chama a API e só ela envia", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo()]));
    m.abordagem.mockResolvedValue(detalhe({ pode_aprovar: true, conferencias: [] }));
    m.aprovarAbordagem.mockResolvedValue(detalhe({ situacao: "Enviada" }));
    render(<Abordagens />);
    const painel = await abrirConta();
    await userEvent.click(within(painel).getByRole("button", { name: "Aprovar e enviar por e-mail" }));
    await waitFor(() => expect(m.aprovarAbordagem).toHaveBeenCalledWith(1));
  });

  it("recusa da API aparece no painel sem perder o texto", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo()]));
    m.abordagem.mockResolvedValue(detalhe({ pode_aprovar: true, conferencias: [] }));
    m.aprovarAbordagem.mockRejectedValue(
      new ErroDaApi(409, "o envio por e-mail não está configurado: preencha CRM_M365_* no .env"),
    );
    render(<Abordagens />);
    const painel = await abrirConta();
    await userEvent.click(within(painel).getByRole("button", { name: "Aprovar e enviar por e-mail" }));
    expect(await within(painel).findByRole("alert")).toHaveTextContent("CRM_M365");
    expect(within(painel).getByLabelText("Mensagem")).toHaveValue("Olá, [nome]. Proponho 30 minutos.");
  });

  it("WhatsApp aprovado libera o link e a pessoa marca como enviada", async () => {
    m.abordagens.mockResolvedValue(pagina([resumo({ canal: "WhatsApp", situacao: "Aprovada" })]));
    m.abordagem.mockResolvedValue(
      detalhe({
        canal: "WhatsApp",
        situacao: "Aprovada",
        assunto: null,
        link_whatsapp: "https://wa.me/5521999991234?text=Ol%C3%A1",
      }),
    );
    m.marcarAbordagemEnviada.mockResolvedValue(detalhe({ situacao: "Enviada" }));
    render(<Abordagens />);
    const painel = await abrirConta();
    expect(within(painel).getByRole("link", { name: "Abrir no WhatsApp" })).toHaveAttribute(
      "href",
      "https://wa.me/5521999991234?text=Ol%C3%A1",
    );
    expect(within(painel).queryByLabelText("Assunto")).not.toBeInTheDocument();
    await userEvent.click(within(painel).getByRole("button", { name: "Marcar como enviada" }));
    await waitFor(() => expect(m.marcarAbordagemEnviada).toHaveBeenCalledWith(1));
  });

  it("conta bloqueada só prepara depois de ter quem apresenta", async () => {
    m.abordagens.mockResolvedValue(
      pagina([resumo({ situacao: "Bloqueada", quem_apresenta: null })]),
    );
    m.abordagem.mockResolvedValue(
      detalhe({ situacao: "Bloqueada", quem_apresenta: null, ficha: null, mensagem: null, versao: 0 }),
    );
    m.editarAbordagem.mockResolvedValue(detalhe());
    m.prepararAbordagem.mockResolvedValue(detalhe({ situacao: "Pesquisando" }));
    render(<Abordagens />);
    const painel = await abrirConta();
    const preparar = within(painel).getByRole("button", { name: "Preparar a ficha" });
    expect(preparar).toBeDisabled();

    await userEvent.type(within(painel).getByLabelText("Quem apresenta"), "Parceira B");
    await userEvent.click(preparar);
    await waitFor(() => expect(m.prepararAbordagem).toHaveBeenCalledWith(1));
    expect(m.editarAbordagem).toHaveBeenCalledWith(1, { quem_apresenta: "Parceira B" });
  });
});

describe("meses", () => {
  it("nome curto do mês", () => {
    expect(nomeDoMes("2026-10")).toBe("outubro/26");
  });

  it("escolhe o mês atual, senão o próximo, senão o último", () => {
    const hoje = new Date(2026, 8, 26);
    expect(mesPadrao(["2026-09", "2026-10"], hoje)).toBe("2026-09");
    expect(mesPadrao(["2026-10", "2026-11"], hoje)).toBe("2026-10");
    expect(mesPadrao(["2026-07", "2026-08"], hoje)).toBe("2026-08");
    expect(mesPadrao([], hoje)).toBeNull();
  });
});

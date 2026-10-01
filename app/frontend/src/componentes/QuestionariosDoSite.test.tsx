import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { QuestionarioDaOportunidade as Questionario, QuestionarioResumo } from "../api/tipos";
import { QuestionarioDaOportunidade } from "./QuestionarioDaOportunidade";
import { BotaoBuscarQuestionarios, QuestionariosDoSite, usarQuestionarios } from "./QuestionariosDoSite";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      questionarios: vi.fn(), buscarQuestionarios: vi.fn(), resolverQuestionario: vi.fn(), questionarioDaOportunidade: vi.fn(),
    },
  };
});

const resumo = (o: Partial<QuestionarioResumo>): QuestionarioResumo => ({
  id: 1, recebido_em: "2026-09-30T16:40:00", razao_social: "Exemplo Alfa Comércio Ltda", nome_fantasia: "Exemplo Alfa",
  cnpj: "12345678000190", contato_nome: "Ana Souza", contato_cargo: "Diretora Financeira", situacao: "Importado",
  cliente_novo: true, o_que_fez: 'Criou grupo, empresa, contato e a oportunidade em "Enviar proposta".', grupo_id: 5,
  grupo_nome: "Exemplo Alfa", oportunidade_id: 10, oportunidade_em_aberto_id: null, porte_crm: "Pequeno",
  porte_site: "Pequeno", tem_pdf: true, ...o,
});
const ALFA = resumo({});
const BETA = resumo({
  id: 2, razao_social: "Exemplo Beta Serviços SA", cliente_novo: false, oportunidade_id: 11, porte_crm: "Médio",
  porte_site: "Pequeno", o_que_fez: 'Entrou no grupo "Grupo Exemplo Beta"; criou a oportunidade e o contato.',
});
const GAMA = resumo({
  id: 3, razao_social: "Exemplo Gama Indústria Ltda", cliente_novo: false, situacao: "Precisa de você", oportunidade_id: null,
  oportunidade_em_aberto_id: 7, o_que_fez: "Já existe oportunidade em aberto para este CNPJ.",
});

function Tela({ aoAbrir = vi.fn(), aoMudar = vi.fn() }: { aoAbrir?: (id: number) => void; aoMudar?: () => void }) {
  const estado = usarQuestionarios(aoMudar);
  return (
    <>
      <BotaoBuscarQuestionarios estado={estado} />
      <QuestionariosDoSite estado={estado} aoAbrir={aoAbrir} />
    </>
  );
}

describe("Questionários do site no Funil", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.questionarios).mockResolvedValue([]);
  });

  it("busca e diz o que o CRM fez com cada um, sem estado só por cor", async () => {
    vi.mocked(api.buscarQuestionarios).mockResolvedValue({ buscado_em: "2026-10-01T09:12:00", novos: [ALFA, BETA, GAMA], avisos: [] });
    const aoMudar = vi.fn();
    render(<Tela aoMudar={aoMudar} />);
    await userEvent.click(screen.getByRole("button", { name: "Buscar questionários" }));

    expect(await screen.findByRole("status")).toHaveTextContent("3 questionários novos. 1 precisa de você.");
    const alfa = screen.getByText("Exemplo Alfa Comércio Ltda").closest("tr")!;
    expect(alfa).toHaveTextContent("cliente novo");
    expect(alfa).toHaveTextContent("CNPJ 12.345.678/0001-90 · Ana Souza, Diretora Financeira");
    expect(alfa).toHaveTextContent("igual ao do questionário");
    const beta = screen.getByText("Exemplo Beta Serviços SA").closest("tr")!;
    expect(beta).toHaveTextContent("empresa já no CRM");
    expect(beta).toHaveTextContent("questionário dizia Pequeno: a régua do CRM vale");
    expect(screen.getByText("Exemplo Gama Indústria Ltda").closest("tr")).toHaveTextContent("precisa de você");
    expect(aoMudar).toHaveBeenCalled();
  });

  it("abre a oportunidade criada", async () => {
    vi.mocked(api.buscarQuestionarios).mockResolvedValue({ buscado_em: "2026-10-01T09:12:00", novos: [ALFA], avisos: [] });
    const aoAbrir = vi.fn();
    render(<Tela aoAbrir={aoAbrir} />);
    await userEvent.click(screen.getByRole("button", { name: "Buscar questionários" }));
    await userEvent.click(await screen.findByRole("button", { name: "Abrir oportunidade" }));
    expect(aoAbrir).toHaveBeenCalledWith(10);
  });

  it("o que precisa de você aparece ao abrir o Funil e é resolvido ali", async () => {
    vi.mocked(api.questionarios).mockResolvedValue([GAMA, ALFA]);
    vi.mocked(api.resolverQuestionario).mockResolvedValue({ ...GAMA, situacao: "Importado", oportunidade_id: 7, o_que_fez: "Anexado à oportunidade." });
    render(<Tela />);
    expect(await screen.findByText("Exemplo Gama Indústria Ltda")).toBeInTheDocument();
    expect(screen.queryByText("Exemplo Alfa Comércio Ltda")).toBeNull(); // já resolvido: não polui a tela
    await userEvent.click(screen.getByRole("button", { name: "Anexar à existente" }));
    expect(api.resolverQuestionario).toHaveBeenCalledWith(3, "anexar");
    expect(await screen.findByText("Anexado à oportunidade.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir oportunidade" })).toBeInTheDocument();
  });

  it("nenhum novo diz isso, e avisos aparecem", async () => {
    vi.mocked(api.buscarQuestionarios).mockResolvedValue({ buscado_em: "2026-10-01T09:12:00", novos: [], avisos: ["Questionário x ficou de fora."] });
    render(<Tela />);
    await userEvent.click(screen.getByRole("button", { name: "Buscar questionários" }));
    expect(await screen.findByText(/Nenhum questionário novo no site/)).toBeInTheDocument();
    expect(screen.getByText("⚠ Questionário x ficou de fora.")).toBeInTheDocument();
  });

  it("sem configuração, mostra o que fazer", async () => {
    vi.mocked(api.buscarQuestionarios).mockRejectedValue(new ErroDaApi(409, "Falta configurar a busca: preencha CRM_QUESTIONARIO_URL"));
    render(<Tela />);
    await userEvent.click(screen.getByRole("button", { name: "Buscar questionários" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("CRM_QUESTIONARIO_URL");
  });
});

describe("Questionário na oportunidade", () => {
  const Q: Questionario = {
    id: 4, recebido_em: "2026-09-30T16:40:00", versao: "BPO Full 2026 v6", contato_nome: "Ana Souza", contato_cargo: null,
    contato_email: null, contato_celular: null, servicos: ["Contábil", "Fiscal"], porte_crm: "Pequeno", porte_site: "Micro",
    pontuacao: "1.33", horas_base: 10, nota_complexidade: 2, fatores_complexidade: [{ id: "auditoria", rotulo: "auditoria externa" }],
    nota_risco: 1, fatores_risco: [], pontos_de_atencao: [["Empresa auditada: exigências de fechamento", "Contábil"]],
    notas_emitidas: 40, notas_recebidas: 80, tem_pdf: true,
  };

  it("mostra de onde veio, o PDF, o porte e as notas com o motivo", async () => {
    vi.mocked(api.questionarioDaOportunidade).mockResolvedValue(Q);
    render(<QuestionarioDaOportunidade oportunidadeId={10} />);
    const bloco = await screen.findByRole("region", { name: "Questionário do cliente" });
    expect(screen.getByRole("link", { name: "Ver PDF" })).toHaveAttribute("href", "/api/questionarios/4/pdf");
    expect(bloco).toHaveTextContent("Pequeno · pontuação 1,33 · 10 h base/mês (o questionário dizia Micro)");
    expect(bloco).toHaveTextContent("notas emitidas 40 + recebidas 80");
    expect(bloco).toHaveTextContent("Complexidade 2: auditoria externa · Risco técnico 1: nenhum fator");
    expect(bloco).toHaveTextContent("Contábil: Empresa auditada");
  });

  it("oportunidade sem questionário não mostra nada", async () => {
    vi.mocked(api.questionarioDaOportunidade).mockResolvedValue(null);
    const { container } = render(<QuestionarioDaOportunidade oportunidadeId={10} />);
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
});

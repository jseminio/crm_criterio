import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { QuestionarioResumo } from "../api/tipos";
import { QuestionariosQuePrecisam } from "./QuestionariosQuePrecisam";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { questionarios: vi.fn(), resolverQuestionario: vi.fn() } };
});

const q = (o: Partial<QuestionarioResumo>): QuestionarioResumo => ({
  id: 1, recebido_em: "2026-10-02T17:12:00Z", razao_social: "SMARTHIS LTDA", nome_fantasia: "Smarthis", cnpj: "29862205000168",
  contato_nome: "Ewelyn", contato_cargo: "Controller", situacao: "Precisa de você", cliente_novo: false,
  o_que_fez: "Já havia oportunidade em aberto no grupo.", grupo_id: 1, grupo_nome: "Smarthis", oportunidade_id: null,
  oportunidade_em_aberto_id: 9, porte_crm: "Médio", porte_site: "Médio", tem_pdf: true, ...o,
});

describe("Agenda › questionários que precisam de você", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lista só os que precisam e resolve na própria Agenda", async () => {
    vi.mocked(api.questionarios).mockResolvedValueOnce([q({}), q({ id: 2, situacao: "Oportunidade criada", razao_social: "Outra" })])
      .mockResolvedValueOnce([]);
    vi.mocked(api.resolverQuestionario).mockResolvedValue(q({ situacao: "Anexado" }));
    render(<QuestionariosQuePrecisam />);
    expect(await screen.findByRole("heading", { name: "! Questionários que precisam de você · 1" })).toBeInTheDocument();
    expect(screen.getByText("Smarthis")).toBeInTheDocument();
    expect(screen.queryByText("Outra")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Anexar à existente" }));
    expect(api.resolverQuestionario).toHaveBeenCalledWith(1, "anexar");
    expect(await screen.findByRole("status")).toHaveTextContent("anexado à oportunidade que já existia");
  });

  it("sem nenhum pendente, não aparece", async () => {
    vi.mocked(api.questionarios).mockResolvedValue([q({ situacao: "Oportunidade criada" })]);
    const { container } = render(<QuestionariosQuePrecisam />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container).toBeEmptyDOMElement();
  });
});

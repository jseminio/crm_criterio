import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso, ReuniaoDeResultado } from "../api/tipos";
import { PainelEmCurso, textoDaAta } from "./PainelEmCurso";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: { reunioesDoGrupo: vi.fn(), registrarReuniao: vi.fn(), montarAta: vi.fn(), responsaveisPorAjuste: vi.fn() },
  };
});

const F: Funil = {
  etapas: [], checklist: {},
  tipos: [
    { chave: "mensal", nome: "Mensal", meses: 1, participantes: "Gestor & Cliente", pauta: ["Demonstrações do mês"] },
    { chave: "trimestral", nome: "Trimestral", meses: 3, participantes: "Gestor & Cliente", pauta: ["PRA e KPIs"] },
  ],
  cadencia: { B: ["trimestral"] }, grupos: [],
};

const G: GrupoNoFunilDoSucesso = {
  grupo_id: 7, nome: "Rede Farma", etapa: "em_curso", classe: "B", itens_feitos: [], etapa_desde: null, em_curso_desde: null,
  situacao: "atrasada", reunioes: [{ tipo: "trimestral", ultima: null, proxima: null, atrasada: true, dias_de_atraso: null }],
  ajustes_pendentes: 2, ajustes_atrasados: 1, ajustes_feitos: 1,
};

const TRANSCRICAO = "Cliente: o frete está em custo, precisa ir para despesa. Gestor: anotado, ajustamos até sexta.";

const REUNIAO: ReuniaoDeResultado = {
  id: 1, tipo: "trimestral", data: "2026-10-01", participantes: "Gestor e CFO", pauta: null, dashboard: null,
  resumo: "Reunião boa.", decisoes: "• Abrir loja", pendencias_do_cliente: "• Extratos", pontos_sensiveis: null,
  proximos_passos: null, tem_transcricao: true, registrada_por: "Eduardo Luiz", criado_em: "2026-10-01T15:00:00+00:00",
  ajustes: [{
    id: 9, reuniao_id: 1, reuniao_tipo: "trimestral", reuniao_data: "2026-10-01", grupo_id: 7, grupo_nome: "Rede Farma",
    descricao: "Reclassificar o frete", responsavel_email: "bruno@grupocriterio.com.br", responsavel_nome: "Bruno Soares",
    prazo: "2026-10-10", feito_em: null, feito_por: null, observacao: null,
  }],
};

const painel = () => render(<PainelEmCurso f={F} g={G} titulo="Rede Farma" subtitulo="Em curso" aoFechar={() => {}} aoMudar={() => {}} />);

describe("Ata da reunião pela transcrição do Granola (02/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.reunioesDoGrupo).mockResolvedValue([]);
    vi.mocked(api.responsaveisPorAjuste).mockResolvedValue([
      { email: "bruno@grupocriterio.com.br", nome: "Bruno Soares", perfil: "Área técnica" },
      { email: "jefferson@grupocriterio.com.br", nome: "Jefferson Souza", perfil: "Área técnica" },
    ]);
  });

  it("monta o rascunho, exige responsável em cada ajuste e registra tudo", async () => {
    vi.mocked(api.montarAta).mockResolvedValue({
      resumo: "O cliente quer abrir loja.", decisoes_do_cliente: ["Abrir a segunda loja"],
      ajustes: [{ descricao: "Reclassificar o frete", prazo: "2026-10-10" }],
      pendencias_do_cliente: ["Enviar extratos"], pontos_sensiveis: [], custo_usd: "0.0800",
    });
    vi.mocked(api.registrarReuniao).mockResolvedValue(G);
    painel();
    const montar = screen.getByRole("button", { name: "Montar a ata com a IA" });
    expect(montar).toBeDisabled(); // sem transcrição
    fireEvent.change(screen.getByLabelText("Transcrição do Granola"), { target: { value: TRANSCRICAO } });
    await userEvent.click(montar);
    expect(api.montarAta).toHaveBeenCalledWith(7, expect.objectContaining({ tipo: "trimestral", transcricao: TRANSCRICAO }));
    expect(await screen.findByText(/custo estimado US\$ 0,0800/)).toBeInTheDocument();
    expect(screen.getByLabelText("Resumo")).toHaveValue("O cliente quer abrir loja.");
    expect(screen.getByLabelText("Decisões do cliente")).toHaveValue("• Abrir a segunda loja");
    expect(screen.getByLabelText("Ajuste 1: o quê")).toHaveValue("Reclassificar o frete");
    const registrar = screen.getByRole("button", { name: "Registrar reunião" });
    expect(registrar).toBeDisabled();
    expect(screen.getByText("· cada ajuste precisa de descrição e responsável")).toBeInTheDocument();
    await userEvent.selectOptions(await screen.findByLabelText("Ajuste 1: responsável"), "bruno@grupocriterio.com.br");
    await userEvent.click(screen.getByRole("button", { name: "+ ajuste" }));
    fireEvent.change(screen.getByLabelText("Ajuste 2: o quê"), { target: { value: "Conciliar o cartão" } });
    await userEvent.selectOptions(screen.getByLabelText("Ajuste 2: responsável"), "jefferson@grupocriterio.com.br");
    await userEvent.click(registrar);
    expect(api.registrarReuniao).toHaveBeenCalledWith(7, expect.objectContaining({
      resumo: "O cliente quer abrir loja.", pendencias_do_cliente: "• Enviar extratos", transcricao: TRANSCRICAO,
      ajustes: [
        { descricao: "Reclassificar o frete", responsavel_email: "bruno@grupocriterio.com.br", prazo: "2026-10-10" },
        { descricao: "Conciliar o cartão", responsavel_email: "jefferson@grupocriterio.com.br", prazo: null },
      ],
    }));
    expect(await screen.findByText(/com 2 ajustes enviados à área técnica/)).toBeInTheDocument();
    expect(screen.getByLabelText("Transcrição do Granola")).toHaveValue("");
  });

  it("a falha da IA aparece e nada se perde", async () => {
    vi.mocked(api.montarAta).mockRejectedValue(new ErroDaApi(502, "A chave da API da Anthropic não está no .env"));
    painel();
    fireEvent.change(screen.getByLabelText("Transcrição do Granola"), { target: { value: TRANSCRICAO } });
    await userEvent.click(screen.getByRole("button", { name: "Montar a ata com a IA" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A chave da API");
    expect(screen.getByLabelText("Transcrição do Granola")).toHaveValue(TRANSCRICAO);
  });

  it("sem ninguém com o perfil da área técnica, avisa onde liberar", async () => {
    vi.mocked(api.responsaveisPorAjuste).mockResolvedValue([]);
    painel();
    expect(await screen.findByText(/Ninguém ainda pode receber ajustes/)).toBeInTheDocument();
  });

  it("o histórico mostra a ata com os ajustes e copia o texto", async () => {
    vi.mocked(api.reunioesDoGrupo).mockResolvedValue([REUNIAO]);
    const escrever = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: escrever } });
    painel();
    const item = (await screen.findByText("Trimestral · 01/10/2026")).closest("li")!;
    expect(within(item).getByText(/Reclassificar o frete — Bruno Soares/)).toBeInTheDocument();
    expect(within(item).getByText(/com a transcrição do Granola guardada/)).toBeInTheDocument();
    expect(screen.getByText(/Ajustes da área técnica: 3 · 1 feito · ⚠ 1 atrasado/)).toBeInTheDocument();
    await userEvent.click(within(item).getByRole("button", { name: "Copiar a ata" }));
    expect(escrever).toHaveBeenCalledWith(textoDaAta(F, "Rede Farma", REUNIAO));
    expect(await within(item).findByRole("button", { name: "✓ Ata copiada" })).toBeInTheDocument();
  });

  it("o texto da ata traz os ajustes com responsável e prazo", () => {
    const texto = textoDaAta(F, "Rede Farma", REUNIAO);
    expect(texto).toContain("Ata da reunião trimestral · Rede Farma · 01/10/2026");
    expect(texto).toContain("Ajustes para a área técnica\n• Reclassificar o frete — Bruno Soares, até 10/10/2026");
    expect(texto).toContain("Pendências do cliente\n• Extratos");
    expect(texto).not.toContain("Pontos sensíveis");
  });
});

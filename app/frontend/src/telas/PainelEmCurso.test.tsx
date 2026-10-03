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
    api: { reunioesDoGrupo: vi.fn(), registrarReuniao: vi.fn(), montarAta: vi.fn(), responsaveisPorAjuste: vi.fn(), servicos: vi.fn() },
  };
});

const F: Funil = {
  etapas: [], checklist: {},
  tipos: [
    { chave: "mensal", nome: "Mensal", meses: 1, participantes: "Gestor & Cliente", pauta: ["Demonstrações do mês"] },
    { chave: "trimestral", nome: "Trimestral", meses: 3, participantes: "Gestor & Cliente", pauta: ["PRA e KPIs"] },
  ],
  tipos_antigos: { anual: "Anual" }, cadencia: { B: ["trimestral"] }, intencao: {}, grupos: [],
  carteira: { nome: "Bimestral da carteira", participantes: "Head do BPO & CEO da Critério", pauta: [], ultima: null,
    proxima: "2026-12-02", atrasada: false, dias_de_atraso: null },
};

const servico = (nome: string, recorrente: boolean, temas: string[] = []) => ({
  nome, nome_por_extenso: null, linha: recorrente ? "C1" as const : "C2" as const, recorrente, para_quem: "", perguntas: [],
  fora_do_perfil: [], transbordo: "", nomes_antigos: [], rascunho: false, temas: temas.map((t) => ({ nome: t, perguntas: [] })),
});
const CATALOGO = [
  servico("BPO Financeiro", true), servico("Consultoria", false, ["Tributária e fiscal", "Valuation, PPA e laudos"]),
  servico("Auditoria", false),
];

const G: GrupoNoFunilDoSucesso = {
  grupo_id: 7, nome: "Rede Farma", etapa: "em_curso", classe: "B", itens_feitos: [], etapa_desde: null, em_curso_desde: null,
  situacao: "atrasada", reunioes: [{ tipo: "trimestral", ultima: null, proxima: null, atrasada: true, dias_de_atraso: null }],
  ajustes_pendentes: 2, ajustes_atrasados: 1, ajustes_feitos: 1,
  mrr_bruto: "5000.00", vendas_abertas: 0, vendas_por_mes: "0", vendas_em_projeto: "0",
};

const TRANSCRICAO = "Cliente: o frete está em custo, precisa ir para despesa. Gestor: anotado, ajustamos até sexta.";

const REUNIAO: ReuniaoDeResultado = {
  id: 1, tipo: "trimestral", data: "2026-10-01", participantes: "Gestor e CFO", pauta: null, dashboard: null,
  resumo: "Reunião boa.", decisoes: "• Abrir loja", pendencias_do_cliente: "• Extratos", pontos_sensiveis: null,
  proximos_passos: null, tem_transcricao: true, registrada_por: "Eduardo Luiz", criado_em: "2026-10-01T15:00:00+00:00",
  estrategia_e_desafios: "Abrir a segunda loja",
  oportunidades: [
    { id: 3, lacuna: "Ninguém faz projeção de caixa", servico: "BPO Financeiro", servico_tema: null, valor: "4500.00",
      recorrente: true, oportunidade_id: 40, situacao: "Enviar proposta" },
    { id: 4, lacuna: "Balanço sem auditoria", servico: "Auditoria", servico_tema: null, valor: null,
      recorrente: false, oportunidade_id: null, situacao: null },
  ],
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
    vi.mocked(api.servicos).mockResolvedValue(CATALOGO);
  });

  it("monta o rascunho com o responsável lido da ata, exige responsável em cada ajuste e registra tudo", async () => {
    vi.mocked(api.montarAta).mockResolvedValue({
      resumo: "O cliente quer abrir loja.", decisoes_do_cliente: ["Abrir a segunda loja"],
      ajustes: [
        { descricao: "Reclassificar o frete", prazo: "2026-10-10", responsavel_citado: "Bruno",
          responsavel_email: "bruno@grupocriterio.com.br", trecho: "Bruno fica com o frete até dia 10" },
        { descricao: "Revisar o fluxo de caixa", prazo: null, responsavel_citado: "Carla", responsavel_email: null, trecho: null },
      ],
      pendencias_do_cliente: ["Enviar extratos"], pontos_sensiveis: [], estrategia_e_desafios: "Abrir a segunda loja",
      oportunidades: [], custo_usd: "0.0800",
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
    expect(screen.getByLabelText("Estratégia e desafios do cliente")).toHaveValue("Abrir a segunda loja");
    // o responsável citado e cadastrado já vem escolhido; o citado sem cadastro pede escolha
    expect(screen.getByLabelText("Ajuste 1: responsável")).toHaveValue("bruno@grupocriterio.com.br");
    expect(screen.getByText("✓ responsável e prazo lidos da ata (“Bruno fica com o frete até dia 10”)")).toBeInTheDocument();
    expect(screen.getByLabelText("Ajuste 2: responsável")).toHaveValue("");
    expect(screen.getByText(/⚠ citado na ata: “Carla”, que não está entre quem recebe ajustes/)).toBeInTheDocument();
    const registrar = screen.getByRole("button", { name: "Registrar reunião" });
    expect(registrar).toBeDisabled();
    expect(screen.getByText("· cada ajuste precisa de descrição e responsável")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Ajuste 2: responsável"), "jefferson@grupocriterio.com.br");
    await userEvent.click(screen.getByRole("button", { name: "+ ajuste" }));
    fireEvent.change(screen.getByLabelText("Ajuste 3: o quê"), { target: { value: "Conciliar o cartão" } });
    await userEvent.selectOptions(screen.getByLabelText("Ajuste 3: responsável"), "jefferson@grupocriterio.com.br");
    await userEvent.click(registrar);
    expect(api.registrarReuniao).toHaveBeenCalledWith(7, expect.objectContaining({
      resumo: "O cliente quer abrir loja.", pendencias_do_cliente: "• Enviar extratos", transcricao: TRANSCRICAO,
      estrategia_e_desafios: "Abrir a segunda loja",
      ajustes: [
        { descricao: "Reclassificar o frete", responsavel_email: "bruno@grupocriterio.com.br", prazo: "2026-10-10" },
        { descricao: "Revisar o fluxo de caixa", responsavel_email: "jefferson@grupocriterio.com.br", prazo: null },
        { descricao: "Conciliar o cartão", responsavel_email: "jefferson@grupocriterio.com.br", prazo: null },
      ],
      oportunidades: [],
    }));
    expect(await screen.findByText(/com 3 ajustes enviados à área técnica\./)).toBeInTheDocument();
    expect(screen.getByLabelText("Transcrição do Granola")).toHaveValue("");
  });

  it("oportunidades: a IA sugere, o “+” abre outra, e as marcadas vão para o Funil comercial", async () => {
    vi.mocked(api.montarAta).mockResolvedValue({
      resumo: "", decisoes_do_cliente: [], ajustes: [], pendencias_do_cliente: [], pontos_sensiveis: [], estrategia_e_desafios: "",
      oportunidades: [
        { lacuna: "Ninguém faz projeção de caixa", servico: "BPO Financeiro", servico_tema: null, valor: "4500.00",
          recorrente: true, trecho: "a equipe financeira é só uma pessoa" },
        // serviço fora do catálogo volta vazio: a pessoa escolhe
        { lacuna: "Avaliar a empresa antes do sócio", servico: null, servico_tema: null, valor: null, recorrente: false, trecho: null },
      ],
      custo_usd: null,
    });
    vi.mocked(api.registrarReuniao).mockResolvedValue(G);
    painel();
    expect(screen.getByText("Nenhuma oportunidade. Monte a ata com a IA ou inclua no “+”.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Transcrição do Granola"), { target: { value: TRANSCRICAO } });
    await userEvent.click(screen.getByRole("button", { name: "Montar a ata com a IA" }));
    expect(await screen.findByText("Oportunidades de novos negócios · 2")).toBeInTheDocument();
    expect(screen.getByText("1 · BPO Financeiro · recorrente")).toBeInTheDocument();
    expect(screen.getByLabelText("Oportunidade 1: valor por mês")).toHaveValue("4.500,00");
    expect(screen.getByText("✓ lido da ata (“a equipe financeira é só uma pessoa”)")).toBeInTheDocument();
    expect(screen.getByText("2 · nova")).toBeInTheDocument();
    const registrar = screen.getByRole("button", { name: "Registrar reunião" });
    expect(registrar).toBeDisabled();
    expect(screen.getByText("· a oportunidade 2 precisa de lacuna e serviço, ou sai no ✕")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Oportunidade 2: serviço"), "Consultoria|Valuation, PPA e laudos");
    expect(screen.getByText("2 · Consultoria · Valuation, PPA e laudos · projeto")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Oportunidade 2: valor total"), { target: { value: "14.000" } });
    // o "+" abre outra, vazia; sem serviço trava o registro até escolher ou tirar
    await userEvent.click(screen.getByRole("button", { name: "Novo serviço a vender" }));
    expect(screen.getByText("Oportunidades de novos negócios · 3")).toBeInTheDocument();
    expect(registrar).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Oportunidade 3: lacuna"), { target: { value: "Balanço sem auditoria" } });
    await userEvent.selectOptions(screen.getByLabelText("Oportunidade 3: serviço"), "Auditoria|");
    await userEvent.click(screen.getAllByLabelText(/Abrir no Funil comercial/)[2]);
    expect(screen.getByText("· abre 2 oportunidades no Funil comercial")).toBeInTheDocument();
    await userEvent.click(registrar);
    expect(api.registrarReuniao).toHaveBeenCalledWith(7, expect.objectContaining({
      oportunidades: [
        { lacuna: "Ninguém faz projeção de caixa", servico: "BPO Financeiro", servico_tema: null, valor: "4500.00", abrir_no_funil: true },
        { lacuna: "Avaliar a empresa antes do sócio", servico: "Consultoria", servico_tema: "Valuation, PPA e laudos", valor: "14000", abrir_no_funil: true },
        { lacuna: "Balanço sem auditoria", servico: "Auditoria", servico_tema: null, valor: null, abrir_no_funil: false },
      ],
    }));
    expect(await screen.findByText(/registrada, com 2 oportunidades abertas no Funil comercial\./)).toBeInTheDocument();
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
    expect(within(item).getByText(/Ninguém faz projeção de caixa/)).toBeInTheDocument();
    expect(within(item).getByText("só anotada")).toBeInTheDocument();
    // as vendas abertas ficam no topo do histórico, com a situação no Funil comercial
    expect(screen.getByText("Vendas abertas nas reuniões")).toBeInTheDocument();
    expect(screen.getByText(/BPO Financeiro — Enviar proposta · R\$\s4\.500,00\/mês/)).toBeInTheDocument();
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
    expect(texto).toContain("Estratégia e desafios do cliente\nAbrir a segunda loja");
    expect(texto).toMatch(/Oportunidades de novos negócios\n• BPO Financeiro: Ninguém faz projeção de caixa \(R\$\s4\.500,00\/mês\)\n• Auditoria: Balanço sem auditoria/);
    expect(texto).not.toContain("Pontos sensíveis");
  });
});

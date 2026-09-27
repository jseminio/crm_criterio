import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { AnaliseDaCarteira, ClassificacaoDaCarteira, ItemDaCarteira } from "../api/tipos";
import { Carteira } from "./Carteira";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      classificacaoDaCarteira: vi.fn(),
      analiseDaCarteira: vi.fn(),
      gerarAnaliseDaCarteira: vi.fn(),
      revisoesDaCarteira: vi.fn().mockResolvedValue([]),
      registrarRevisaoDaCarteira: vi.fn(),
      editarMesDaRevisao: vi.fn(),
    },
  };
});

const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.00", classe: "B", classe_efetiva: "B1",
  alerta_de_churn: null, em_cobranca: false, eixo_de_acao: "Sem urgência de churn", semaforo: 1, churn: 1,
  sem_contrato_ativo: false, empresas: [], ...o,
});
const classificacao = (o: Partial<ClassificacaoDaCarteira> = {}): ClassificacaoDaCarteira => ({
  referencia: "2026-07-31", versao_dos_parametros: "v1",
  isc: { valor: "53.65", zona: "atenção", componente_classe: "59.45", componente_semaforo: "42.33", componente_churn: "59.01", receita_total: "1000.00", grupos: 1, fora_do_isc: 0 },
  retrato: { unidades: 1, receita_total: "1000.00", grupos_travados: 0, receita_travada: "0.00", percentual_travado: "0.0" },
  por_classe: { B: 1 }, itens: [item()], avisos: [], ...o,
});
const analise = (o: Partial<AnaliseDaCarteira> = {}): AnaliseDaCarteira => ({
  texto: "A carteira está na zona de atenção, puxada pela inadimplência.",
  gerada_em: "2026-09-27T08:12:00+00:00", gerada_por: "Eduardo Luiz", modelo: "claude-sonnet-5", custo_usd: "0.0042", ...o,
});

async function abrir() {
  vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(classificacao());
  render(<Carteira />);
  await screen.findByText(/▸ Alfa/);
}

describe("Análise da carteira escrita pela IA", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem análise ainda, avisa e mantém o botão desabilitado até digitar o nome", async () => {
    vi.mocked(api.analiseDaCarteira).mockResolvedValue(null);
    await abrir();
    expect(await screen.findByText(/Nenhuma análise gerada ainda/)).toBeInTheDocument();
    const botao = screen.getByRole("button", { name: "Gerar análise" });
    expect(botao).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Quem está gerando"), "Eduardo Luiz");
    expect(botao).toBeEnabled();
  });

  it("mostra a análise já gerada, com quem gerou e quando", async () => {
    vi.mocked(api.analiseDaCarteira).mockResolvedValue(analise());
    await abrir();
    expect(await screen.findByText(/zona de atenção, puxada pela inadimplência/)).toBeInTheDocument();
    expect(screen.getByText(/por Eduardo Luiz/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gerar de novo" })).toBeInTheDocument();
  });

  it("gerar chama a API com o autor e recarrega o resultado", async () => {
    vi.mocked(api.analiseDaCarteira).mockResolvedValueOnce(null).mockResolvedValueOnce(analise());
    vi.mocked(api.gerarAnaliseDaCarteira).mockResolvedValue(analise());
    await abrir();
    await screen.findByText(/Nenhuma análise gerada ainda/);
    await userEvent.type(screen.getByLabelText("Quem está gerando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Gerar análise" }));
    await waitFor(() => expect(api.gerarAnaliseDaCarteira).toHaveBeenCalledWith("Eduardo Luiz"));
    expect(await screen.findByText(/zona de atenção, puxada pela inadimplência/)).toBeInTheDocument();
  });

  it("mostra o erro da API sem travar a tela", async () => {
    vi.mocked(api.analiseDaCarteira).mockResolvedValue(null);
    vi.mocked(api.gerarAnaliseDaCarteira).mockRejectedValue(new ErroDaApi(502, "A Anthropic recusou a chave da API."));
    await abrir();
    await screen.findByText(/Nenhuma análise gerada ainda/);
    await userEvent.type(screen.getByLabelText("Quem está gerando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Gerar análise" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/recusou a chave/);
  });
});

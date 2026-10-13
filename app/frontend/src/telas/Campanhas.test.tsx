/** A aba Campanhas (13/10/2026): funil por canal, decisão por campanha e os estados da tela. */

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { EtapaDoCanal, FunilDoCanal, PainelDeCampanhas, PainelDoSdr } from "../api/tipos";
import { Campanhas } from "./Campanhas";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { campanhas: vi.fn(), painelDoSdr: vi.fn() } };
});

const taxa = (numerador: number, denominador: number) => ({
  numerador, denominador, valor: denominador ? (100 * numerador) / denominador : null,
});

const ROTULOS = [["leads", "Leads"], ["icp", "No ICP"], ["qualificados", "Qualificados"],
  ["reunioes", "Reuniões"], ["propostas", "Propostas"], ["contratos", "Contratos"]];

function funil(canal: string, qs: number[], investimento: number | null): FunilDoCanal {
  const etapas: EtapaDoCanal[] = qs.map((q, i) => ({
    chave: ROTULOS[i][0], rotulo: ROTULOS[i][1], quantidade: q,
    passagem: i + 1 < qs.length ? taxa(qs[i + 1], q) : null,
    custo: investimento !== null && q ? (investimento / q).toFixed(2) : null,
  }));
  return {
    canal, investimento: investimento === null ? null : investimento.toFixed(2), etapas,
    mrr_novo: "7583.33", contratos_sem_preco: 0,
    cac: investimento !== null && qs[5] ? (investimento / qs[5]).toFixed(2) : null,
    lead_a_contrato: taxa(qs[5], qs[0]),
  };
}

function painel(extra: Partial<PainelDeCampanhas> = {}): PainelDeCampanhas {
  return {
    mes: "2026-10",
    leads: 180,
    total: funil("Tráfego pago · total", [180, 75, 46, 26, 11, 3], 12000),
    canais: [funil("Meta Ads", [120, 42, 24, 12, 5, 1], 6000), funil("Google Ads", [60, 33, 22, 14, 6, 2], 6000)],
    campanhas: [{
      canal: "Meta Ads", campanha: "Tempo para Crescer", leads: 80, no_icp: taxa(22, 80), qualificados: taxa(10, 80),
      reunioes: 4, contratos: 0, mrr_novo: "0.00", descartes: [{ nome: "Porte abaixo do mínimo", quantidade: 22 }],
      decisao: "Refazer público", porque: "28% no ICP, abaixo do alvo de 40%; o que mais tira é “Porte abaixo do mínimo”.",
    }],
    regua: { volume_minimo: 20, icp_alvo_pct: "40", qualificados_meta_pct: 20, qualificados_alerta_pct: 10 },
    prontidao: [
      { ok: true, texto: "Investimento do mês lançado em todos os canais" },
      { ok: false, texto: "Leitura automática do Meta Ads e do Google Ads ainda não ligada" },
    ],
    ...extra,
  };
}

const sdr = { leads: 100, responderam: 61, primeira_resposta: { valor: 240 },
  qualificados_sobre_responderam: taxa(30, 61) } as unknown as PainelDoSdr;

describe("Campanhas", () => {
  beforeEach(() => {
    vi.mocked(api.campanhas).mockReset();
    vi.mocked(api.painelDoSdr).mockReset().mockResolvedValue(sdr);
  });

  it("mostra um funil por canal, com o total, a passagem e o custo de cada etapa", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    render(<Campanhas />);
    const meta = await screen.findByRole("figure", { name: "Funil de Meta Ads" });
    expect(screen.getByRole("figure", { name: "Funil de Tráfego pago · total" })).toBeInTheDocument();
    expect(within(meta).getByText(/↓ 35%/)).toBeInTheDocument();
    expect(within(meta).getByText(/R\$\s?50,00 por lead$/)).toBeInTheDocument();
    expect(within(meta).getByText(/R\$\s?500,00 por reunião/)).toBeInTheDocument();
    expect(within(meta).getByText("· pior passagem")).toBeInTheDocument();
    expect(api.painelDoSdr).toHaveBeenCalledWith({ mes: expect.any(String), origem: "trafego_pago" });
  });

  it("diz a decisão em palavra e o porquê", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    render(<Campanhas />);
    const tabela = await screen.findByRole("table", { name: "Decisão por campanha" });
    expect(within(tabela).getByText("Refazer público")).toHaveClass("etiqueta-perda");
    expect(within(tabela).getByText(/abaixo do alvo de 40%/)).toBeInTheDocument();
    expect(screen.getByText(/decide com 20 leads ou mais/)).toBeInTheDocument();
  });

  it("sem investimento, o custo vira frase e não zero", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel({
      total: funil("Tráfego pago · total", [10, 5, 2, 1, 0, 0], null), canais: [funil("Meta Ads", [10, 5, 2, 1, 0, 0], null)],
    }));
    render(<Campanhas />);
    expect(await screen.findAllByText("Sem investimento lançado")).toHaveLength(3);
    expect(screen.queryByText(/R\$\s?0,00 por/)).not.toBeInTheDocument();
  });

  it("mostra a prontidão dos dados, com palavra além do sinal", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    render(<Campanhas />);
    expect(await screen.findByText(/Leitura automática do Meta Ads/)).toBeInTheDocument();
    expect(screen.getByText("Falta:")).toBeInTheDocument();
    expect(screen.getByText("Pronto:")).toBeInTheDocument();
  });

  it("vazio: explica como o lead de tráfego pago entra", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel({ leads: 0, total: null, canais: [], campanhas: [] }));
    render(<Campanhas />);
    expect(await screen.findByText(/Nenhum lead de tráfego pago/)).toBeInTheDocument();
    expect(screen.getByText(/Custos e mídia/)).toBeInTheDocument();
  });

  it("erro: oferece tentar de novo", async () => {
    vi.mocked(api.campanhas).mockRejectedValue(new ErroDaApi(500, "falhou"));
    render(<Campanhas />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});

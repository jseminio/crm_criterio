/** A aba Campanhas (13/10/2026): funil por canal, decisão por campanha e os estados da tela. */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { EtapaDoCanal, FunilDoCanal, PainelDeCampanhas, PainelDoSdr, ResumoDasConversoes } from "../api/tipos";
import { Campanhas } from "./Campanhas";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { campanhas: vi.fn(), painelDoSdr: vi.fn(), atualizarDosAnuncios: vi.fn(), conversoes: vi.fn(), enviarConversoes: vi.fn(),
    leadsDoMeta: vi.fn(), buscarLeadsDoMeta: vi.fn() } };
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
      investimento: "3000.00", fonte: "lido", custo_por_lead_icp: "136.36", custo_por_reuniao: "750.00",
    }],
    regua: { volume_minimo: 20, icp_alvo_pct: "40", qualificados_meta_pct: 20, qualificados_alerta_pct: 10, teto_de_custo: "1.5" },
    anuncios: [
      { canal: "Meta Ads", configurada: true, lido_em: "2026-10-13T22:40:00Z" },
      { canal: "Google Ads", configurada: true, lido_em: null },
    ],
    prontidao: [
      { ok: true, texto: "Investimento do mês lançado em todos os canais" },
      { ok: false, texto: "Leitura automática do Meta Ads e do Google Ads ainda não ligada" },
    ],
    ...extra,
  };
}

function resumo(extra: Partial<ResumoDasConversoes> = {}): ResumoDasConversoes {
  const linha = (evento: string, rotulo: string, plataforma: string, enviados: number, sem: number, valor: number | null = null) =>
    ({ evento, rotulo, plataforma, enviados, recusados: 0, falhas: 0, sem_identificador: sem, valor_enviado: valor });
  return {
    mes: "2026-10",
    ligadas: { "Meta Ads": true, "Google Ads": false },
    linhas: [
      linha("lead_qualificado", "Lead qualificado", "Meta Ads", 18, 0), linha("lead_qualificado", "Lead qualificado", "Google Ads", 0, 7),
      linha("contrato_fechado", "Contrato fechado", "Meta Ads", 2, 0, 15166.66), linha("contrato_fechado", "Contrato fechado", "Google Ads", 0, 1),
    ],
    recusas: [{ lead: "Acme", evento: "Lead qualificado", plataforma: "Meta Ads", motivo: "O evento tem mais de 7 dias: o Meta não aceita.", em: "2026-10-14T12:00:00Z" }],
    ultima_rodada: { em: "2026-10-14T12:20:00Z", plataformas: [] },
    ...extra,
  };
}

const sdr = { leads: 100, responderam: 61, primeira_resposta: { valor: 240 },
  qualificados_sobre_responderam: taxa(30, 61) } as unknown as PainelDoSdr;

describe("Campanhas", () => {
  beforeEach(() => {
    vi.mocked(api.campanhas).mockReset();
    vi.mocked(api.painelDoSdr).mockReset().mockResolvedValue(sdr);
    vi.mocked(api.conversoes).mockReset().mockResolvedValue(resumo());
    vi.mocked(api.enviarConversoes).mockReset();
    vi.mocked(api.leadsDoMeta).mockReset().mockResolvedValue({ ligada: false, ultima: null });
    vi.mocked(api.buscarLeadsDoMeta).mockReset();
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
    expect(screen.getByText(/lance o investimento do mês em SDR da IA › Custos e mídia/)).toBeInTheDocument();
  });

  it("erro: oferece tentar de novo", async () => {
    vi.mocked(api.campanhas).mockRejectedValue(new ErroDaApi(500, "falhou"));
    render(<Campanhas />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("mostra o custo por campanha e de onde veio", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    render(<Campanhas />);
    const tabela = await screen.findByRole("table", { name: "Decisão por campanha" });
    expect(within(tabela).getByText(/R\$\s?750,00/)).toBeInTheDocument();
    expect(within(tabela).getByText(/R\$\s?136,36/)).toBeInTheDocument();
    expect(within(tabela).getByText("Meta Ads · lido")).toBeInTheDocument();
    expect(screen.getByText(/rever custo acima de 1,5 ×/)).toBeInTheDocument();
  });

  it("um botão lê as duas plataformas e diz o resultado de cada uma", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    vi.mocked(api.atualizarDosAnuncios).mockResolvedValue({
      plataformas: [
        { canal: "Meta Ads", ok: true, lidas: 3, gravadas: 2, digitadas_mantidas: ["Vale"], erro: null },
        { canal: "Google Ads", ok: false, lidas: 0, gravadas: 0, digitadas_mantidas: [],
          erro: "O Google Ads recusou o acesso (HTTP 403): token de teste" },
      ],
      lido_em: "2026-10-14T12:00:00Z",
    });
    render(<Campanhas />);
    expect(await screen.findByText(/Meta Ads lido em .* · Google Ads ainda não lido neste mês/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Atualizar do Meta Ads" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Atualizar dos anúncios" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Meta Ads: 2 campanha(s) atualizada(s). Valor digitado mantido em: Vale.");
    expect(screen.getByRole("alert")).toHaveTextContent("Google Ads: O Google Ads recusou o acesso");
    expect(api.campanhas).toHaveBeenCalledTimes(2);
  });

  it("falha geral vira frase, e sem nenhuma leitura ligada não há botão", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    vi.mocked(api.atualizarDosAnuncios).mockRejectedValue(new ErroDaApi(409, "nenhuma leitura de anúncios está ligada"));
    const { unmount } = render(<Campanhas />);
    fireEvent.click(await screen.findByRole("button", { name: "Atualizar dos anúncios" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nenhuma leitura de anúncios está ligada");
    unmount();
    vi.mocked(api.campanhas).mockResolvedValue(painel({ anuncios: [
      { canal: "Meta Ads", configurada: false, lido_em: null }, { canal: "Google Ads", configurada: false, lido_em: null },
    ] }));
    render(<Campanhas />);
    expect(await screen.findByText(/Google Ads: leitura desligada/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Atualizar dos anúncios" })).not.toBeInTheDocument();
  });

  it("mostra as conversões devolvidas por evento e plataforma, e as recusas com o motivo", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    render(<Campanhas />);
    const tabela = await screen.findByRole("table", { name: "Conversões devolvidas" });
    expect(within(tabela).getByText("18 enviados")).toBeInTheDocument();
    expect(within(tabela).getByText(/2 enviados · R\$\s?15\.166,66/)).toBeInTheDocument();
    expect(within(tabela).getByText("0 enviados · 7 sem gclid")).toBeInTheDocument();
    expect(screen.getByText(/Meta Ads: ligada · Google Ads: desligada/)).toBeInTheDocument();
    expect(screen.getByText(/Acme · Lead qualificado · Meta Ads: O evento tem mais de 7 dias/)).toBeInTheDocument();
    expect(screen.getByText(/só criptografados \(SHA-256\)/)).toBeInTheDocument();
  });

  it("enviar agora roda uma vez e mostra o aviso de credencial recusada", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    vi.mocked(api.enviarConversoes).mockResolvedValue({ em: "2026-10-14T12:30:00Z", plataformas: [] });
    render(<Campanhas />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar agora" }));
    await waitFor(() => expect(api.conversoes).toHaveBeenCalledTimes(2));
    vi.mocked(api.conversoes).mockResolvedValue(resumo({ ultima_rodada: { em: "2026-10-14T12:30:00Z", plataformas: [
      { plataforma: "Meta Ads", ligada: true, enviados: 0, recusados: 0, falhas: 0, aviso: "A Meta recusou o token." }] } }));
    fireEvent.click(screen.getByRole("button", { name: "Enviar agora" }));
    expect(await screen.findByText("Meta Ads: A Meta recusou o token.")).toBeInTheDocument();
  });

  it("devolução desligada: sem botão, com o caminho para ligar", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    vi.mocked(api.conversoes).mockResolvedValue(resumo({ ligadas: { "Meta Ads": false, "Google Ads": false }, ultima_rodada: null }));
    render(<Campanhas />);
    expect(await screen.findByText("Devolução desligada em Configurações › Integrações")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enviar agora" })).not.toBeInTheDocument();
  });

  it("leads do Meta: mostra a última busca e busca agora", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    vi.mocked(api.leadsDoMeta).mockResolvedValue({ ligada: true, ultima: { em: "2026-10-14T12:40:00Z", ligada: true, lidos: 3, novos: 3, erro: null } });
    vi.mocked(api.buscarLeadsDoMeta).mockResolvedValue({ em: "2026-10-14T12:50:00Z", ligada: true, lidos: 4, novos: 1, erro: null });
    render(<Campanhas />);
    expect(await screen.findByText(/Leads do Meta: busca automática a cada 10 minutos · última em .*, 3 novos/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Buscar leads agora" }));
    expect(await screen.findByText("1 lead novo do Meta.")).toBeInTheDocument();
    expect(api.campanhas).toHaveBeenCalledTimes(2);
  });

  it("leads do Meta: desligada sem botão, e erro da Meta em frase", async () => {
    vi.mocked(api.campanhas).mockResolvedValue(painel());
    const { unmount } = render(<Campanhas />);
    expect(await screen.findByText("Leads do Meta: entrada desligada em Configurações › Integrações")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Buscar leads agora" })).not.toBeInTheDocument();
    unmount();
    vi.mocked(api.leadsDoMeta).mockResolvedValue({ ligada: true, ultima: { em: "2026-10-14T12:40:00Z", ligada: true, lidos: 0, novos: 0,
      erro: "A Meta recusou o token da página (HTTP 400): Invalid token" } });
    render(<Campanhas />);
    expect(await screen.findByText(/recusou o token da página/)).toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { AbaDaAssinatura, EnvioParaAssinatura, Eu } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { AssinaturaEletronica } from "./AssinaturaEletronica";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      assinaturaDoContrato: vi.fn(), enviarParaAssinatura: vi.fn(), conferirAssinatura: vi.fn(),
      lembrarSignatario: vi.fn(), cancelarAssinatura: vi.fn(),
    },
  };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };
const LEITURA: Eu = { ...ADMIN, perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const ABA: AbaDaAssinatura = {
  ligada: true, ambiente: "sandbox", autenticacao: "email", pede_telefone: false, problema: null,
  prazo_sugerido: "2026-11-17", atual: null, anteriores: [],
  sugeridos: [
    { nome: "Sócio Exemplo", email: "socio@grupocriterio.com.br", telefone: null, papel: "Contratada", origem: "configurações" },
    { nome: "Maria Decisora", email: "maria@clientea.com.br", telefone: null, papel: "Contratante", origem: "contato decisor" },
  ],
};

const envio = (o: Partial<EnvioParaAssinatura> = {}): EnvioParaAssinatura => ({
  id: 3, origem: "crm", situacao: "em_assinatura", situacao_texto: "Em assinatura", ambiente: "sandbox",
  nome_arquivo: "CONT CCE RJ1 102.2026.pdf", prazo: "2026-11-17", enviado_em: "2026-10-18T17:00:00Z",
  enviado_por: "Eduardo", concluido_em: null, motivo: null, ultimo_evento: null, ultimo_evento_em: null,
  documento_anexado_id: null,
  signatarios: [
    { nome: "Sócio Exemplo", email: "socio@grupocriterio.com.br", telefone: null, papel: "Contratada", assinou_em: "2026-10-18T17:02:00Z" },
    { nome: "Maria Decisora", email: "maria@clientea.com.br", telefone: null, papel: "Contratante", assinou_em: null },
  ],
  ...o,
});

function abrir(eu: Eu = ADMIN, aoAssinar = vi.fn()) {
  render(<ProvedorDeAcesso eu={eu}><AssinaturaEletronica contratoId={7} aoAssinar={aoAssinar} /></ProvedorDeAcesso>);
  return aoAssinar;
}

describe("Assinatura eletrônica pela Clicksign (18/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("desligada, explica onde ligar e não mostra o envio", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue({ ...ABA, ligada: false, problema: "Assinatura eletrônica desligada: ligue em Configurações › Integrações › Clicksign." });
    abrir();
    expect(await screen.findByText(/Integrações › Clicksign/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enviar para assinatura" })).not.toBeInTheDocument();
  });

  it("sugere os signatários com a origem e não envia sem o PDF", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue(ABA);
    abrir();
    expect(await screen.findByDisplayValue("Maria Decisora")).toBeInTheDocument();
    expect(screen.getByText("do contato decisor")).toBeInTheDocument();
    expect(screen.getByText(/Sandbox: teste, sem validade jurídica/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enviar para assinatura" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Escolha o PDF final");
    expect(api.enviarParaAssinatura).not.toHaveBeenCalled();
  });

  it("envia o PDF com os signatários, inclusive uma testemunha", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue(ABA);
    vi.mocked(api.enviarParaAssinatura).mockResolvedValue({ ...ABA, problema: "Já há um envio em assinatura.", atual: envio() });
    abrir();
    await screen.findByDisplayValue("Maria Decisora");
    const pdf = new File(["%PDF-1.7"], "CONT CCE RJ1 102.2026.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("Documento final (PDF)"), pdf);
    await userEvent.click(screen.getByRole("button", { name: "+ Signatário ou testemunha" }));
    await userEvent.type(screen.getByLabelText("Nome do signatário 3"), "Ana Testemunha");
    await userEvent.type(screen.getByLabelText("E-mail do signatário 3"), "ana@x.com");
    await userEvent.click(screen.getByRole("button", { name: "Enviar para assinatura" }));
    await waitFor(() => expect(api.enviarParaAssinatura).toHaveBeenCalled());
    const [id, corpo] = vi.mocked(api.enviarParaAssinatura).mock.calls[0];
    expect(id).toBe(7);
    expect(corpo.nome_arquivo).toBe("CONT CCE RJ1 102.2026.pdf");
    expect(corpo.conteudo_base64).toMatch(/^data:application\/pdf;base64,/);
    expect(corpo.prazo).toBe("2026-11-17");
    expect(corpo.signatarios.map((s) => s.papel)).toEqual(["Contratada", "Contratante", "Testemunha"]);
    expect(await screen.findByText("⏳ Em assinatura · 1 de 2")).toBeInTheDocument();
    expect(screen.getByText(/⏳ Pendente/)).toBeInTheDocument();
  });

  it("em assinatura: reenvia o aviso só a quem falta", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue({ ...ABA, problema: "Já há um envio em assinatura.", atual: envio() });
    vi.mocked(api.lembrarSignatario).mockResolvedValue({ ...ABA, problema: "Já há um envio em assinatura.", atual: envio() });
    abrir();
    const botoes = await screen.findAllByRole("button", { name: "Reenviar aviso" });
    expect(botoes).toHaveLength(1);
    await userEvent.click(botoes[0]);
    expect(api.lembrarSignatario).toHaveBeenCalledWith(7, "maria@clientea.com.br");
    expect(await screen.findByText("✓ Aviso reenviado para Maria Decisora.")).toBeInTheDocument();
  });

  it("conferir que encontra assinado avisa o painel e aponta o PDF na seção Documento assinado", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue({ ...ABA, problema: "Já há um envio em assinatura.", atual: envio() });
    const assinado = envio({ situacao: "assinado", situacao_texto: "Assinado", concluido_em: "2026-10-20T15:00:00Z", documento_anexado_id: 9 });
    vi.mocked(api.conferirAssinatura).mockResolvedValue({ ...ABA, problema: "O contrato está Ativo.", atual: assinado });
    const aoAssinar = abrir();
    await userEvent.click(await screen.findByRole("button", { name: "Conferir na Clicksign" }));
    expect(await screen.findByText("✓ Assinado por todos em 20/10/2026")).toBeInTheDocument();
    expect(aoAssinar).toHaveBeenCalled();
    expect(screen.getByText(/está na seção Documento assinado/)).toHaveTextContent(/ativou o contrato/);
  });

  it("envelope feito fora do CRM: aparece, mas não se lembra nem cancela por aqui", async () => {
    const fora = envio({ origem: "fora", enviado_por: "direto na Clicksign", prazo: null });
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue({ ...ABA, problema: "Já há um envelope em assinatura.", atual: fora });
    abrir();
    expect(await screen.findByText(/feito direto na Clicksign/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar aviso" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar envio" })).not.toBeInTheDocument();
  });

  it("quem só vê não envia nem cancela", async () => {
    vi.mocked(api.assinaturaDoContrato).mockResolvedValue({ ...ABA, problema: "Já há um envio em assinatura.", atual: envio() });
    abrir(LEITURA);
    expect(await screen.findByText("⏳ Em assinatura · 1 de 2")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar envio" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar aviso" })).not.toBeInTheDocument();
  });
});

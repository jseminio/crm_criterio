import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { LinkDoGrupo, ProvedorDeCards } from "./AberturaDeCard";
import { Modal } from "./Modal";
import { QuadroDeLacunas } from "./Lacunas";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      grupo: vi.fn().mockResolvedValue({ id: 7, nome: "Grupo Atlântica", situacao: "Cliente", origem: "Carga 2026",
        responsavel_cs: null, observacao: null, data_entrada: null, fundido_em_id: null, quantas_oportunidades: 0 }),
      oportunidades: vi.fn().mockResolvedValue({ total: 0, itens: [] }),
      grupos: vi.fn().mockResolvedValue({ total: 0, itens: [] }),
      lacunas: vi.fn().mockResolvedValue([{ cadastro: "Cliente", registro_id: 7, registro: "Grupo Atlântica",
        campo: "Responsável de CS", chave: "responsavel_cs", obrigatorio: true, grupo_id: 7, empresa_id: null, contrato_id: null }]),
    },
  };
});

describe("O nome na composição abre o card do grupo (18/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem grupo (lead) fica só o texto", () => {
    render(<ProvedorDeCards listas={null}><LinkDoGrupo grupoId={null} nome="Lead do site" /></ProvedorDeCards>);
    expect(screen.getByText("Lead do site").tagName).not.toBe("BUTTON");
  });

  it("abre o card por cima da composição, com o que falta; Esc fecha só o card", async () => {
    const fecharComposicao = vi.fn();
    render(
      <ProvedorDeCards listas={null}>
        <Modal titulo="MRR novo" aoFechar={fecharComposicao}>
          <LinkDoGrupo grupoId={7} nome="Grupo Atlântica" />
        </Modal>
      </ProvedorDeCards>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Grupo Atlântica" }));
    const card = await screen.findByRole("dialog", { name: "Grupo Atlântica" });
    expect(api.grupo).toHaveBeenCalledWith(7);
    expect(card.closest(".camada-do-card")).not.toBeNull();
    expect(await within(card).findByText(/O que falta no cadastro · 1 obrigatório/)).toBeInTheDocument();
    expect(within(card).getByText("Obrigatório em falta: responsável de CS")).toBeInTheDocument();
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Grupo Atlântica" })).toBeNull();
    expect(fecharComposicao).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "MRR novo" })).toBeInTheDocument();
  });
});

describe("QuadroDeLacunas", () => {
  const l = (chave: string, obrigatorio: boolean) => ({ cadastro: "Contrato" as const, registro_id: 3, registro: "X · BPO",
    campo: chave, chave, obrigatorio, grupo_id: 1, empresa_id: null, contrato_id: 3 });

  it("obrigatório primeiro, com nível em texto; o que não tem campo diz onde se preenche", async () => {
    const aoIr = vi.fn();
    render(<QuadroDeLacunas lacunas={[l("signatario", false), l("empresa_id", true)]} aoIr={aoIr}
      semCampo={(x) => (x.chave === "empresa_id" ? "O CNPJ do contrato não se edita neste card." : null)} />);
    expect(screen.getByText("O que falta no cadastro · 1 obrigatório e 1 prioritário")).toBeInTheDocument();
    const itens = screen.getAllByRole("listitem");
    expect(itens[0]).toHaveTextContent("Obrigatórioempresa_idO CNPJ do contrato não se edita neste card.");
    await userEvent.click(within(itens[1]).getByRole("button", { name: "ir ao campo" }));
    expect(aoIr).toHaveBeenCalledWith(expect.objectContaining({ chave: "signatario" }));
  });

  it("sem resposta da API, não mostra nada; com a lista vazia, diz que está completo", () => {
    const { container, rerender } = render(<QuadroDeLacunas lacunas={null} aoIr={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<QuadroDeLacunas lacunas={[]} aoIr={vi.fn()} />);
    expect(screen.getByText("Cadastro completo")).toBeInTheDocument();
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProvedorDeAcesso } from "../entrada";
import { SdrEAbordagens } from "./SdrEAbordagens";

vi.mock("./Abordagens", () => ({ Abordagens: () => <p>tela de abordagens</p> }));
vi.mock("./Sdr", () => ({ Sdr: () => <p>tela da SDR de IA</p> }));

const eu = (permissoes: string[]) => ({
  modo: "microsoft" as const, email: "x@grupocriterio.com.br", nome: "X", perfil: "P", administrador: false, permissoes,
});

describe("SDR · Abordagens e conhecimento (02/10/2026)", () => {
  beforeEach(() => localStorage.clear());

  it("junta Abordagens e SDR da IA em abas", () => {
    render(<SdrEAbordagens listas={null} />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Abordagens", "SDR da IA"]);
    expect(screen.getByText("tela de abordagens")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "SDR da IA" }));
    expect(screen.getByText("tela da SDR de IA")).toBeInTheDocument();
    expect(screen.getByText(/quantos a IA qualificou/)).toBeInTheDocument();
  });

  it("cada aba só aparece para quem pode vê-la", () => {
    render(
      <ProvedorDeAcesso eu={eu(["sdr.ver"])}>
        <SdrEAbordagens listas={null} />
      </ProvedorDeAcesso>,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["SDR da IA"]);
    expect(screen.getByText("tela da SDR de IA")).toBeInTheDocument();
  });
});

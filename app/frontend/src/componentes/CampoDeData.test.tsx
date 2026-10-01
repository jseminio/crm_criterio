/** Campo de data no padrão brasileiro, independente do idioma do navegador (01/10/2026). */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { brParaIso, isoParaBr, mascarar } from "../dataBr";
import { CampoDeData } from "./CampoDeData";

describe("conversões", () => {
  it("ISO <-> dd/mm/aaaa, recusando data que não existe", () => {
    expect(isoParaBr("2026-08-01")).toBe("01/08/2026");
    expect(isoParaBr("")).toBe("");
    expect(brParaIso("01/08/2026")).toBe("2026-08-01");
    expect(brParaIso("31/02/2026")).toBeNull();
    expect(brParaIso("01/08")).toBeNull();
  });

  it("as barras entram sozinhas", () => {
    expect(mascarar("0108")).toBe("01/08");
    expect(mascarar("01082026")).toBe("01/08/2026");
    expect(mascarar("01/08/2026999")).toBe("01/08/2026");
  });
});

describe("CampoDeData", () => {
  it("mostra dd/mm/aaaa e devolve ISO ao digitar só os números", async () => {
    const aoMudar = vi.fn();
    render(<><label htmlFor="d">Data</label><CampoDeData id="d" value="2026-03-01" aoMudar={aoMudar} /></>);
    const campo = screen.getByLabelText("Data");
    expect(campo).toHaveValue("01/03/2026");
    await userEvent.clear(campo);
    expect(aoMudar).toHaveBeenLastCalledWith("");
    await userEvent.type(campo, "15042026");
    expect(campo).toHaveValue("15/04/2026");
    expect(aoMudar).toHaveBeenLastCalledWith("2026-04-15");
  });

  it("data que não existe avisa e não é repassada", async () => {
    const aoMudar = vi.fn();
    render(<><label htmlFor="d">Data</label><CampoDeData id="d" value="" aoMudar={aoMudar} /></>);
    await userEvent.type(screen.getByLabelText("Data"), "31022026");
    expect(screen.getByRole("alert")).toHaveTextContent("Data inválida");
    expect(aoMudar).not.toHaveBeenCalled();
  });

  it("o calendário em português escolhe o dia", async () => {
    const aoMudar = vi.fn();
    render(<CampoDeData value="2026-08-10" aoMudar={aoMudar} aria-label="Data" />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir calendário" }));
    expect(screen.getByText("Agosto 2026")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Próximo mês" }));
    await userEvent.click(screen.getByRole("button", { name: "05/09/2026" }));
    expect(aoMudar).toHaveBeenLastCalledWith("2026-09-05");
    expect(screen.getByLabelText("Data")).toHaveValue("05/09/2026");
    expect(screen.queryByRole("dialog", { name: "Calendário" })).toBeNull();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Recolhivel } from "./Recolhivel";

describe("Recolhivel", () => {
  it("só monta o conteúdo depois de aberto", async () => {
    const monta = vi.fn();
    const Filho = () => { monta(); return <p>conteúdo</p>; };
    render(<Recolhivel titulo="Recortes do funil" resumo="por serviço"><Filho /></Recolhivel>);
    expect(screen.getByText("Recortes do funil")).toBeInTheDocument();
    expect(screen.getByText(/por serviço/)).toBeInTheDocument();
    expect(monta).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Recortes do funil"));
    expect(await screen.findByText("conteúdo")).toBeInTheDocument();
    expect(monta).toHaveBeenCalled();
  });
});

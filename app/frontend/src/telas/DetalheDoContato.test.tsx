import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { EntidadeDeContato, Listas, PessoaDeContato } from "../api/tipos";
import { DetalheDoContato } from "./DetalheDoContato";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { criarContato: vi.fn(), editarContato: vi.fn(), editarEmpresa: vi.fn(), criarEmpresaDoGrupo: vi.fn() } };
});

const LISTAS = { papeis_de_contato: ["Decisor", "Ponto focal"] } as unknown as Listas;
const E = { logradouro: null, numero: null, complemento: null, bairro: null, municipio: null, uf: null, cep: null };
const p = (o: Partial<PessoaDeContato> = {}): PessoaDeContato => ({
  id: 5, nome: "Maria", cargo: null, email: "m@a.com", telefone: null, papel: null, observacao: null,
  nao_contatar: false, empresa_id: 10, grupo_id: null, do_grupo: false, ...o,
});
const ent = (o: Partial<EntidadeDeContato> = {}): EntidadeDeContato => ({
  tipo: "cliente", grupo_id: 1, grupo_nome: "Grupo Alfa", empresa_id: 10, razao_social: "Alfa Ltda", nome_fantasia: null,
  cnpj: "11222333000181", endereco: E, mensalidade: "1500.00", propostas: 0, contatos: [], lacunas: ["Contato"], ...o,
});
const abrir = (e = ent(), aoMudar = vi.fn()) => {
  render(<DetalheDoContato entidade={e} listas={LISTAS} aoFechar={vi.fn()} aoMudar={aoMudar} />);
  return aoMudar;
};

describe("DetalheDoContato", () => {
  beforeEach(() => vi.clearAllMocks());

  it("adiciona contato na empresa e avisa a lista para recarregar", async () => {
    vi.mocked(api.criarContato).mockResolvedValue(p());
    const aoMudar = abrir();
    await userEvent.type(screen.getByLabelText("Nome", { selector: "#nova-nome" }), "  Ana  ");
    await userEvent.type(screen.getByLabelText("E-mail", { selector: "#nova-email" }), "ana@x.com");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar contato" }));
    await waitFor(() => expect(api.criarContato).toHaveBeenCalledWith(expect.objectContaining({ nome: "Ana", email: "ana@x.com", empresa_id: 10, nao_contatar: false })));
    expect(aoMudar).toHaveBeenCalled();
  });

  it("o botão de adicionar só libera com o nome preenchido", () => {
    abrir();
    expect(screen.getByRole("button", { name: "Adicionar contato" })).toBeDisabled();
  });

  it("prospect sem empresa liga o contato ao grupo", async () => {
    vi.mocked(api.criarContato).mockResolvedValue(p({ empresa_id: null, grupo_id: 1 }));
    abrir(ent({ tipo: "prospect", empresa_id: null, razao_social: null }));
    await userEvent.type(screen.getByLabelText("Nome", { selector: "#nova-nome" }), "Bia");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar contato" }));
    await waitFor(() => expect(api.criarContato).toHaveBeenCalledWith(expect.objectContaining({ nome: "Bia", grupo_id: 1 })));
    expect((vi.mocked(api.criarContato).mock.calls[0][0] as Record<string, unknown>).empresa_id).toBeUndefined();
  });

  it("prospect sem empresa oferece cadastrar a empresa antes do endereço", async () => {
    vi.mocked(api.criarEmpresaDoGrupo).mockResolvedValue({ id: 99, razao_social: "x", cnpj: null });
    const aoMudar = abrir(ent({ tipo: "prospect", empresa_id: null, razao_social: null }));
    expect(screen.queryByLabelText("Logradouro")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar empresa" }));
    await waitFor(() => expect(api.criarEmpresaDoGrupo).toHaveBeenCalledWith(1));
    expect(aoMudar).toHaveBeenCalled();
  });

  it("mostra os contatos, o do grupo marcado e o 'não contatar'", () => {
    abrir(ent({ contatos: [p(), p({ id: 6, nome: "João", do_grupo: true, nao_contatar: true })], lacunas: [] }));
    expect(screen.getByText("Contato e endereço completos.")).toBeInTheDocument();
    expect(screen.getByText(/do grupo/)).toBeInTheDocument();
    expect(screen.getByText("Não contatar")).toBeInTheDocument();
  });

  it("edita um contato existente", async () => {
    vi.mocked(api.editarContato).mockResolvedValue(p());
    abrir(ent({ contatos: [p()] }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const tel = screen.getByLabelText("Telefone", { selector: "#p5-tel" });
    await userEvent.type(tel, "21 88888-0000");
    await userEvent.click(screen.getByRole("button", { name: "Salvar contato" }));
    await waitFor(() => expect(api.editarContato).toHaveBeenCalledWith(5, expect.objectContaining({ telefone: "21 88888-0000", nome: "Maria" })));
  });

  it("salva o endereço da empresa, vazio vira null", async () => {
    vi.mocked(api.editarEmpresa).mockResolvedValue(E);
    abrir();
    await userEvent.type(screen.getByLabelText("Logradouro"), "Rua Ação");
    await userEvent.selectOptions(screen.getByLabelText("UF"), "RJ");
    await userEvent.click(screen.getByRole("button", { name: /salvar empresa e endereço/i }));
    await waitFor(() => expect(api.editarEmpresa).toHaveBeenCalledWith(10, expect.objectContaining({ logradouro: "Rua Ação", uf: "RJ", cep: null, complemento: null })));
    expect(await screen.findByText("Salvo.")).toBeInTheDocument();
  });

  it("mostra o erro do servidor (CNPJ repetido) sem perder o que foi digitado", async () => {
    vi.mocked(api.editarEmpresa).mockRejectedValue(new ErroDaApi(409, "este CNPJ já está cadastrado em outra empresa"));
    abrir();
    await userEvent.click(screen.getByRole("button", { name: /salvar empresa e endereço/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cnpj já está cadastrado/i);
  });
});

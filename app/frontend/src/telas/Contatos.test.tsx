import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { EntidadeDeContato, PessoaComOrigem, PessoaDeContato } from "../api/tipos";
import { Contatos } from "./Contatos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      contatosPorEmpresa: vi.fn(), contatosPorPessoa: vi.fn(), criarContato: vi.fn(), editarContato: vi.fn(),
      editarEmpresa: vi.fn(), criarEmpresaDoGrupo: vi.fn(),
    },
  };
});

const SEM_ENDERECO = { logradouro: null, numero: null, complemento: null, bairro: null, municipio: null, uf: null, cep: null };
const pessoa = (o: Partial<PessoaDeContato> = {}): PessoaDeContato => ({
  id: 1, nome: "Maria Silva", cargo: "Sócia", email: "maria@alfa.com", telefone: "2199", papel: null, observacao: null,
  nao_contatar: false, empresa_id: 10, grupo_id: null, do_grupo: false, ...o,
});
const entidade = (o: Partial<EntidadeDeContato> = {}): EntidadeDeContato => ({
  tipo: "cliente", grupo_id: 1, grupo_nome: "Grupo Alfa", empresa_id: 10, razao_social: "Alfa Comércio Ltda",
  nome_fantasia: null, cnpj: "11222333000181", endereco: SEM_ENDERECO, mensalidade: "1500.00", recorrente: true, propostas: 0,
  contatos: [], lacunas: ["Contato", "E-mail", "Telefone", "Logradouro", "Município", "UF", "CEP"], ...o,
});
const dePessoa = (o: Partial<PessoaComOrigem> = {}): PessoaComOrigem => ({
  ...pessoa(), tipo: "cliente", grupo_nome: "Grupo Alfa", razao_social: "Alfa Comércio Ltda", ...o,
});

describe("Contatos — clientes e prospects separados", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 1, itens: [entidade()] });
    vi.mocked(api.contatosPorPessoa).mockResolvedValue({ total: 1, itens: [dePessoa()] });
  });

  it("abre em Clientes e mostra a empresa com as lacunas e a mensalidade", async () => {
    render(<Contatos listas={null} />);
    expect(await screen.findByText("Alfa Comércio Ltda")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Clientes" })).toHaveAttribute("aria-selected", "true");
    expect(api.contatosPorEmpresa).toHaveBeenCalledWith("cliente", "", false);
    expect(screen.getByText("7 lacunas")).toBeInTheDocument();
    expect(screen.getByText(/1\.500,00/)).toBeInTheDocument();
  });

  it("a aba Prospects consulta só prospects e mostra propostas em vez de mensalidade", async () => {
    vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 1, itens: [entidade({ tipo: "prospect", empresa_id: null, razao_social: null, cnpj: null, mensalidade: null, propostas: 3, grupo_nome: "Beta Prospect" })] });
    render(<Contatos listas={null} />);
    await userEvent.click(await screen.findByRole("tab", { name: "Prospects" }));
    expect(await screen.findByText("Beta Prospect")).toBeInTheDocument();
    expect(api.contatosPorEmpresa).toHaveBeenLastCalledWith("prospect", "", false);
    expect(screen.getByRole("columnheader", { name: "Propostas" })).toBeInTheDocument();
  });

  it("busca por empresa manda o texto depois que a pessoa para de digitar", async () => {
    render(<Contatos listas={null} />);
    await screen.findByText("Alfa Comércio Ltda");
    await userEvent.type(screen.getByLabelText(/razão social, cnpj ou grupo/i), "alfa");
    await waitFor(() => expect(api.contatosPorEmpresa).toHaveBeenLastCalledWith("cliente", "alfa", false));
  });

  it("trocar para Pessoa busca por nome/e-mail/telefone e mostra as pessoas", async () => {
    render(<Contatos listas={null} />);
    await screen.findByText("Alfa Comércio Ltda");
    await userEvent.click(screen.getByRole("button", { name: "Pessoa" }));
    expect(await screen.findByText("Maria Silva")).toBeInTheDocument();
    expect(screen.getByLabelText(/nome, cargo, e-mail ou telefone/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/nome, cargo/i), "maria");
    await waitFor(() => expect(api.contatosPorPessoa).toHaveBeenLastCalledWith("cliente", "maria"));
  });

  it("'só com lacunas' refaz a consulta com o filtro", async () => {
    render(<Contatos listas={null} />);
    await screen.findByText("Alfa Comércio Ltda");
    await userEvent.click(screen.getByLabelText("Só com lacunas"));
    await waitFor(() => expect(api.contatosPorEmpresa).toHaveBeenLastCalledWith("cliente", "", true));
  });

  it("sem resultado por causa do filtro é diferente de não haver ninguém", async () => {
    vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 0, itens: [] });
    render(<Contatos listas={null} />);
    expect(await screen.findByText(/nenhum cliente cadastrado/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/razão social, cnpj ou grupo/i), "zzz");
    expect(await screen.findByText(/nenhum resultado para esses filtros/i)).toBeInTheDocument();
  });

  it("pessoa com 'não contatar' aparece marcada", async () => {
    vi.mocked(api.contatosPorPessoa).mockResolvedValue({ total: 1, itens: [dePessoa({ nao_contatar: true })] });
    render(<Contatos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Pessoa" }));
    expect(await screen.findByText("Não contatar")).toBeInTheDocument();
  });

  it("cliente não recorrente aparece marcado, com as propostas no lugar da mensalidade", async () => {
    vi.mocked(api.contatosPorEmpresa).mockResolvedValue({
      total: 1,
      itens: [entidade({ empresa_id: null, razao_social: null, cnpj: null, mensalidade: null, recorrente: false, propostas: 2, grupo_nome: "Consultoria Pontual" })],
    });
    render(<Contatos listas={null} />);
    expect(await screen.findByText("Consultoria Pontual")).toBeInTheDocument();
    expect(screen.getByText("Não recorrente")).toBeInTheDocument();
    expect(screen.getByText("2 prop.")).toBeInTheDocument();
  });

  it("cliente recorrente não leva o rótulo", async () => {
    render(<Contatos listas={null} />);
    await screen.findByText("Alfa Comércio Ltda");
    expect(screen.queryByText("Não recorrente")).toBeNull();
  });

  it("abrir a empresa mostra o painel com o que falta", async () => {
    render(<Contatos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alfa Comércio Ltda" }));
    expect(await screen.findByText(/Falta:/)).toBeInTheDocument();
    expect(screen.getByText("Nenhum contato cadastrado ainda.")).toBeInTheDocument();
  });

  describe("Nova pessoa (cadastro direto no menu)", () => {
    const abrir = async () => {
      render(<Contatos listas={null} />);
      await screen.findByText("Alfa Comércio Ltda");
      await userEvent.click(screen.getByRole("button", { name: "Nova pessoa" }));
    };
    const escolherEmpresa = async () => {
      await userEvent.type(screen.getByLabelText(/empresa, cnpj ou grupo/i), "alfa");
      const lista = await screen.findByRole("list", { name: "Resultados da busca" });
      await userEvent.click((await within(lista).findAllByRole("button", { name: "Escolher" }))[0]);
    };

    it("cadastra a pessoa ligada só à empresa escolhida", async () => {
      vi.mocked(api.criarContato).mockResolvedValue(pessoa());
      await abrir();
      await escolherEmpresa();
      await userEvent.type(screen.getByLabelText("Nome"), "João Souza");
      await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
      await waitFor(() => expect(api.criarContato).toHaveBeenCalledTimes(1));
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).toMatchObject({ nome: "João Souza", empresa_id: 10 });
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).not.toHaveProperty("grupo_id");
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    });

    it("pode ligar ao grupo todo", async () => {
      vi.mocked(api.criarContato).mockResolvedValue(pessoa());
      await abrir();
      await escolherEmpresa();
      await userEvent.click(screen.getByRole("radio", { name: /ao grupo todo/i }));
      await userEvent.type(screen.getByLabelText("Nome"), "Ana");
      await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
      await waitFor(() => expect(api.criarContato).toHaveBeenCalled());
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).toMatchObject({ nome: "Ana", grupo_id: 1 });
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).not.toHaveProperty("empresa_id");
    });

    it("prospect sem empresa liga ao grupo, sem perguntar", async () => {
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 1, itens: [entidade({ tipo: "prospect", empresa_id: null, razao_social: null, cnpj: null, grupo_nome: "Beta Prospect", grupo_id: 2 })] });
      vi.mocked(api.criarContato).mockResolvedValue(pessoa());
      render(<Contatos listas={null} />);
      await screen.findByText("Beta Prospect");
      await userEvent.click(screen.getByRole("button", { name: "Nova pessoa" }));
      await userEvent.type(screen.getByLabelText(/empresa, cnpj ou grupo/i), "beta");
      await userEvent.click((await within(await screen.findByRole("list", { name: "Resultados da busca" })).findAllByRole("button", { name: "Escolher" }))[0]);
      expect(screen.queryByRole("radio")).toBeNull();
      await userEvent.type(screen.getByLabelText("Nome"), "Carla");
      await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
      await waitFor(() => expect(api.criarContato).toHaveBeenCalled());
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).toMatchObject({ nome: "Carla", grupo_id: 2 });
    });

    it("não deixa cadastrar sem escolher onde a pessoa trabalha", async () => {
      await abrir();
      expect(screen.queryByRole("button", { name: "Cadastrar pessoa" })).toBeNull();
      expect(screen.getByText("1. Onde esta pessoa trabalha?")).toBeInTheDocument();
    });

    it("avisa quando a busca não acha nada", async () => {
      await abrir();
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 0, itens: [] });
      await userEvent.type(screen.getByLabelText(/empresa, cnpj ou grupo/i), "zzz");
      expect(await screen.findByText(/nada encontrado/i)).toBeInTheDocument();
    });
  });
});

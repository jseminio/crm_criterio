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
      buscarPessoas: vi.fn(), criarEmpresa: vi.fn(), vincularContato: vi.fn(), marcarPrincipal: vi.fn(),
      desvincularContato: vi.fn(), excluirPessoa: vi.fn(), excluirEmpresa: vi.fn(),
      grupos: vi.fn().mockResolvedValue({ total: 0, itens: [] }),
    },
  };
});

const SEM_ENDERECO = { logradouro: null, numero: null, complemento: null, bairro: null, municipio: null, uf: null, cep: null };
const pessoa = (o: Partial<PessoaDeContato> = {}): PessoaDeContato => ({
  id: 1, nome: "Maria Silva", cargo: "Sócia", email: "maria@alfa.com", telefone: "2199", papel: null, observacao: null,
  nao_contatar: false, empresa_id: 10, grupo_id: null, ...o,
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

    it("prospect sem empresa: cria a empresa com o nome do grupo e vincula a pessoa", async () => {
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 1, itens: [entidade({ tipo: "prospect", empresa_id: null, razao_social: null, cnpj: null, grupo_nome: "Beta Prospect", grupo_id: 2 })] });
      vi.mocked(api.criarEmpresaDoGrupo).mockResolvedValue({ id: 88, razao_social: "Beta Prospect", cnpj: null });
      vi.mocked(api.criarContato).mockResolvedValue(pessoa());
      render(<Contatos listas={null} />);
      await screen.findByText("Beta Prospect");
      await userEvent.click(screen.getByRole("button", { name: "Nova pessoa" }));
      await userEvent.type(screen.getByLabelText(/empresa, cnpj ou grupo/i), "beta");
      await userEvent.click((await within(await screen.findByRole("list", { name: "Resultados da busca" })).findAllByRole("button", { name: "Escolher" }))[0]);
      expect(screen.queryByRole("radio")).toBeNull();
      expect(screen.getByText(/será criada com o nome do grupo/)).toBeInTheDocument();
      await userEvent.type(screen.getByLabelText("Nome"), "Carla");
      await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
      await waitFor(() => expect(api.criarContato).toHaveBeenCalled());
      expect(api.criarEmpresaDoGrupo).toHaveBeenCalledWith(2);
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).toMatchObject({ nome: "Carla", empresa_id: 88 });
      expect(vi.mocked(api.criarContato).mock.calls[0][0]).not.toHaveProperty("grupo_id");
    });

    it("cadastra a pessoa sem empresa, na base única de contatos", async () => {
      vi.mocked(api.criarContato).mockResolvedValue(pessoa());
      await abrir();
      expect(screen.getByText("1. Empresa (opcional)")).toBeInTheDocument();
      await userEvent.type(screen.getByLabelText("Nome"), "Livre Silva");
      await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
      await waitFor(() => expect(api.criarContato).toHaveBeenCalledTimes(1));
      const [corpo] = vi.mocked(api.criarContato).mock.calls[0];
      expect(corpo).toMatchObject({ nome: "Livre Silva" });
      expect(corpo).not.toHaveProperty("empresa_id");
      expect(corpo).not.toHaveProperty("grupo_id");
    });

    it("avisa quando a busca não acha nada", async () => {
      await abrir();
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 0, itens: [] });
      await userEvent.type(screen.getByLabelText(/empresa, cnpj ou grupo/i), "zzz");
      expect(await screen.findByText(/nada encontrado/i)).toBeInTheDocument();
    });
  });

  describe("Base única de contatos (30/09/2026)", () => {
    const livre = pessoa({ id: 7, nome: "Livre Silva", email: "livre@x.com", empresa_id: null, empresas: [] });

    it("a pessoa sem empresa aparece como \"Sem empresa\" e abre com as empresas dela", async () => {
      vi.mocked(api.contatosPorPessoa).mockResolvedValue({
        total: 2,
        itens: [
          dePessoa({ id: 7, nome: "Livre Silva", grupo_nome: null, razao_social: null, empresas: [] }),
          dePessoa({ empresas: [
            { empresa_id: 10, razao_social: "Alfa Comércio Ltda", grupo_id: 1, grupo_nome: "Grupo Alfa", principal: true },
            { empresa_id: 11, razao_social: "Delta Ltda", grupo_id: 3, grupo_nome: "Delta Ltda", principal: false },
          ] }),
        ],
      });
      render(<Contatos listas={null} />);
      await userEvent.click(await screen.findByRole("button", { name: "Pessoa" }));
      expect(await screen.findByText(/Sem empresa/)).toBeInTheDocument();
      expect(screen.getByText("★ Alfa Comércio Ltda, Delta Ltda")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Maria Silva" }));
      const empresas = await screen.findByRole("list", { name: "Empresas da pessoa" });
      expect(within(empresas).getAllByRole("listitem")).toHaveLength(2);
      expect(within(empresas).getByText("Principal")).toBeInTheDocument();
    });

    it("Nova empresa vincula um contato já cadastrado, como principal", async () => {
      vi.mocked(api.buscarPessoas).mockResolvedValue([livre]);
      vi.mocked(api.criarEmpresa).mockResolvedValue({ id: 50, razao_social: "Delta", cnpj: null, grupo_id: 9, grupo_nome: "Delta" });
      render(<Contatos listas={null} />);
      await screen.findByText("Alfa Comércio Ltda");
      await userEvent.click(screen.getByRole("button", { name: "Nova empresa" }));
      await userEvent.type(screen.getByLabelText("Razão social"), "Delta Engenharia");
      await userEvent.type(screen.getByLabelText("Município"), "Niterói");
      await userEvent.type(screen.getByLabelText(/buscar por nome, e-mail ou telefone/i), "livre");
      const achados = await screen.findByRole("list", { name: "Contatos encontrados" });
      await userEvent.click(within(achados).getByRole("button", { name: "Vincular" }));
      const vinculados = screen.getByRole("list", { name: "Contatos vinculados" });
      await userEvent.click(within(vinculados).getByRole("checkbox", { name: "Contato principal" }));
      await userEvent.click(screen.getByRole("button", { name: "Salvar empresa" }));
      await waitFor(() => expect(api.criarEmpresa).toHaveBeenCalledTimes(1));
      expect(vi.mocked(api.criarEmpresa).mock.calls[0][0]).toMatchObject({
        razao_social: "Delta Engenharia",
        municipio: "Niterói",
        cnpj: null,
        contatos: [{ pessoa_id: 7, principal: true }],
      });
    });

    it("no painel da empresa marca principal, desvincula e vincula quem já existe", async () => {
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({
        total: 1,
        itens: [entidade({ contatos: [pessoa({ principal: false })] })],
      });
      vi.mocked(api.buscarPessoas).mockResolvedValue([livre]);
      render(<Contatos listas={null} />);
      await userEvent.click((await screen.findAllByRole("button", { name: "Abrir" }))[0]);
      await userEvent.click(screen.getByRole("checkbox", { name: "Contato principal" }));
      await waitFor(() => expect(api.marcarPrincipal).toHaveBeenCalledWith(10, 1, true));
      await userEvent.click(screen.getByRole("button", { name: "Desvincular" }));
      await waitFor(() => expect(api.desvincularContato).toHaveBeenCalledWith(10, 1));
      await userEvent.type(screen.getByLabelText(/buscar por nome, e-mail ou telefone/i), "livre");
      await userEvent.click(await screen.findByRole("button", { name: "Vincular" }));
      await waitFor(() => expect(api.vincularContato).toHaveBeenCalledWith(10, 7));
    });
  });

  describe("Excluir contato e empresa (30/09/2026)", () => {
    it("exclui a empresa só depois de confirmar, avisando que os contatos ficam", async () => {
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({
        total: 1, itens: [entidade({ tem_contrato: false, contatos: [pessoa()] })],
      });
      vi.mocked(api.excluirEmpresa).mockResolvedValue(undefined);
      render(<Contatos listas={null} />);
      await userEvent.click((await screen.findAllByRole("button", { name: "Abrir" }))[0]);
      await userEvent.click(screen.getByRole("button", { name: "Excluir empresa" }));
      expect(api.excluirEmpresa).not.toHaveBeenCalled();
      const dialogo = screen.getByRole("alertdialog", { name: "Excluir empresa" });
      expect(dialogo).toHaveTextContent("1 contato vinculado continua na base");
      expect(dialogo).toHaveTextContent("Não dá para desfazer");
      await userEvent.click(within(dialogo).getByRole("button", { name: "Confirmar" }));
      await waitFor(() => expect(api.excluirEmpresa).toHaveBeenCalledWith(10));
    });

    it("empresa com contrato não oferece a exclusão", async () => {
      vi.mocked(api.contatosPorEmpresa).mockResolvedValue({ total: 1, itens: [entidade({ tem_contrato: true })] });
      render(<Contatos listas={null} />);
      await userEvent.click((await screen.findAllByRole("button", { name: "Abrir" }))[0]);
      expect(screen.queryByRole("button", { name: "Excluir empresa" })).toBeNull();
      expect(screen.getByText(/tem contrato e não pode ser excluída/)).toBeInTheDocument();
    });

    it("cancelar não exclui o contato; confirmar exclui", async () => {
      vi.mocked(api.contatosPorPessoa).mockResolvedValue({
        total: 1,
        itens: [dePessoa({ empresas: [
          { empresa_id: 10, razao_social: "Alfa Comércio Ltda", grupo_id: 1, grupo_nome: "Grupo Alfa", principal: false },
        ] })],
      });
      vi.mocked(api.excluirPessoa).mockResolvedValue(undefined);
      render(<Contatos listas={null} />);
      await userEvent.click(await screen.findByRole("button", { name: "Pessoa" }));
      await userEvent.click(await screen.findByRole("button", { name: "Maria Silva" }));
      await userEvent.click(screen.getByRole("button", { name: "Excluir contato" }));
      expect(screen.getByRole("alertdialog")).toHaveTextContent("Maria Silva sai da base e da empresa Alfa Comércio Ltda.");
      await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
      expect(api.excluirPessoa).not.toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button", { name: "Excluir contato" }));
      await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
      await waitFor(() => expect(api.excluirPessoa).toHaveBeenCalledWith(1));
    });
  });
});

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Alteracao, Eu, MenuDoCatalogo, PerfilDeAcesso, UsuarioDoCrm } from "../api/tipos";
import { ProvedorDeAcesso, SEM_PERMISSAO } from "../entrada";
import { DetalheDaPessoa } from "../telas/DetalheDaPessoa";
import { AlteracoesDoRegistro, HistoricoDeAlteracoes } from "./HistoricoDeAlteracoes";
import { PerfisEAcesso } from "./PerfisEAcesso";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      catalogoDeAcesso: vi.fn(), perfis: vi.fn(), usuarios: vi.fn(), criarPerfil: vi.fn(), mudarPerfil: vi.fn(),
      liberarUsuario: vi.fn(), mudarUsuario: vi.fn(), historico: vi.fn(), editarContato: vi.fn(), excluirPessoa: vi.fn(),
      redefinirSenha: vi.fn(),
    },
  };
});

const CATALOGO: MenuDoCatalogo[] = [
  { chave: "funil", rotulo: "Funil", funcionalidades: [
    { chave: "funil.ver", rotulo: "ver" }, { chave: "funil.editar", rotulo: "criar e editar oportunidade e lead" },
    { chave: "funil.converter", rotulo: "converter em contrato" },
  ] },
  { chave: "carteira", rotulo: "Carteira", funcionalidades: [
    { chave: "carteira.ver", rotulo: "ver" }, { chave: "carteira.exportar", rotulo: "exportar" },
  ] },
];
const ADMIN: PerfilDeAcesso = { id: 1, nome: "Administrador", administrador: true, permissoes: [], pessoas: 1 };
const COMERCIAL: PerfilDeAcesso = { id: 2, nome: "Comercial", administrador: false, permissoes: ["funil.ver", "funil.editar"], pessoas: 1 };
const PESSOAS: UsuarioDoCrm[] = [
  { id: 1, email: "eduardo@grupocriterio.com.br", nome: "Eduardo Luiz", perfil_id: 1, perfil: "Administrador", ativo: true,
    liberado_por: null, criado_em: "2026-10-02T10:00:00" },
  { id: 2, email: "karine@grupocriterio.com.br", nome: null, perfil_id: 2, perfil: "Comercial", ativo: true,
    liberado_por: "Eduardo Luiz", criado_em: "2026-10-02T10:05:00" },
];

describe("Perfis e acesso", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.catalogoDeAcesso).mockResolvedValue(CATALOGO);
    vi.mocked(api.perfis).mockResolvedValue([ADMIN, COMERCIAL]);
    vi.mocked(api.usuarios).mockResolvedValue(PESSOAS);
  });

  it("abre no primeiro perfil que não é o Administrador, com as funcionalidades dele marcadas", async () => {
    render(<PerfisEAcesso />);
    const tabela = await screen.findByRole("table", { name: "Permissões do perfil Comercial" });
    expect(screen.getByRole("tab", { name: /Comercial/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Comercial/ })).toHaveTextContent("✓ Comercial");
    const funil = within(tabela).getByRole("row", { name: /^Funil/ });
    expect(within(funil).getByLabelText("ver")).toBeChecked();
    expect(within(funil).getByLabelText("converter em contrato")).not.toBeChecked();
    expect(within(funil).getByLabelText("Funil: menu inteiro")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Salvar o perfil Comercial" })).toBeDisabled();
  });

  it("o menu inteiro marca todas as funcionalidades dele, e salvar manda a lista", async () => {
    vi.mocked(api.mudarPerfil).mockResolvedValue({ ...COMERCIAL, permissoes: ["carteira.exportar", "carteira.ver", "funil.editar", "funil.ver"] });
    render(<PerfisEAcesso />);
    fireEvent.click(await screen.findByLabelText("Carteira: menu inteiro"));
    expect(screen.getByText("· alterações ainda não salvas")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Salvar o perfil Comercial" }));
    const [id, mudanca] = vi.mocked(api.mudarPerfil).mock.calls[0];
    expect(id).toBe(2);
    expect([...mudanca.permissoes!].sort()).toEqual(["carteira.exportar", "carteira.ver", "funil.editar", "funil.ver"]);
    expect(await screen.findByRole("status")).toHaveTextContent("Perfil Comercial salvo");
  });

  it("o Administrador tem tudo e não se muda", async () => {
    render(<PerfisEAcesso />);
    await userEvent.click(await screen.findByRole("tab", { name: /Administrador/ }));
    expect(screen.getByText(/tem tudo, inclusive o que for criado depois/)).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /Permissões do perfil/ })).toBeNull();
  });

  it("cria perfil e libera uma conta Microsoft com o perfil escolhido", async () => {
    const novo: PerfilDeAcesso = { id: 3, nome: "Customer Success", administrador: false, permissoes: [], pessoas: 0 };
    vi.mocked(api.criarPerfil).mockResolvedValue(novo);
    vi.mocked(api.liberarUsuario).mockResolvedValue({ ...PESSOAS[1], id: 3, email: "ana@grupocriterio.com.br" });
    render(<PerfisEAcesso />);
    await userEvent.type(await screen.findByLabelText("Nome do perfil novo"), "Customer Success");
    vi.mocked(api.perfis).mockResolvedValue([ADMIN, COMERCIAL, novo]);
    await userEvent.click(screen.getByRole("button", { name: "+ Criar perfil" }));
    expect(api.criarPerfil).toHaveBeenCalledWith("Customer Success", []);
    expect(await screen.findByRole("table", { name: "Permissões do perfil Customer Success" })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Conta Microsoft da pessoa"), "ana@grupocriterio.com.br");
    fireEvent.change(screen.getByLabelText("Perfil da pessoa"), { target: { value: "3" } });
    await userEvent.click(screen.getByRole("button", { name: "Liberar acesso" }));
    expect(api.liberarUsuario).toHaveBeenCalledWith("ana@grupocriterio.com.br", 3);
  });

  it("mostra situação com texto e quem liberou, e tirar acesso pede ao servidor", async () => {
    vi.mocked(api.mudarUsuario).mockResolvedValue({ ...PESSOAS[1], ativo: false });
    render(<PerfisEAcesso />);
    const linha = (await screen.findByText("karine@grupocriterio.com.br")).closest("tr")!;
    expect(linha).toHaveTextContent("✓ ativo");
    expect(linha).toHaveTextContent("por Eduardo Luiz");
    await userEvent.click(within(linha).getByRole("button", { name: "tirar acesso" }));
    expect(api.mudarUsuario).toHaveBeenCalledWith(2, { ativo: false });
  });

  it("o erro do servidor aparece com o motivo", async () => {
    const { ErroDaApi } = await import("../api/cliente");
    vi.mocked(api.mudarUsuario).mockRejectedValue(new ErroDaApi(422, "Precisa sobrar pelo menos um Administrador ativo."));
    render(<PerfisEAcesso />);
    const linha = (await screen.findByText("eduardo@grupocriterio.com.br")).closest("tr")!;
    await userEvent.click(within(linha).getByRole("button", { name: "tirar acesso" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Precisa sobrar pelo menos um Administrador ativo.");
  });
});

describe("Perfis e acesso no login com senha (issue #89)", () => {
  const ADMIN_EU: Eu = {
    modo: "senha", email: "eduardo@grupocriterio.com.br", nome: "Eduardo Luiz", perfil: "Administrador", administrador: true, permissoes: [],
  };
  const comSenha = () => render(<ProvedorDeAcesso eu={ADMIN_EU}><PerfisEAcesso /></ProvedorDeAcesso>);

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.catalogoDeAcesso).mockResolvedValue(CATALOGO);
    vi.mocked(api.perfis).mockResolvedValue([ADMIN, COMERCIAL]);
    vi.mocked(api.usuarios).mockResolvedValue(PESSOAS);
  });

  it("cadastra com senha provisória, com o Administrador pré-selecionado", async () => {
    vi.mocked(api.liberarUsuario).mockResolvedValue({ ...PESSOAS[0], id: 3, email: "ana@grupocriterio.com.br" });
    comSenha();
    expect(await screen.findByRole("columnheader", { name: "E-mail" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Conta Microsoft da pessoa")).toBeNull();
    expect(screen.getByLabelText("Perfil da pessoa")).toHaveValue("1");
    await userEvent.type(screen.getByLabelText("E-mail da pessoa"), "ana@grupocriterio.com.br");
    const cadastrar = screen.getByRole("button", { name: "Cadastrar pessoa" });
    expect(cadastrar).toBeDisabled(); // a senha provisória é obrigatória

    await userEvent.type(screen.getByLabelText("Senha provisória"), "curta");
    await userEvent.click(cadastrar);
    expect(screen.getByRole("alert")).toHaveTextContent("Senha provisória: A senha precisa ter pelo menos 8 caracteres.");
    expect(api.liberarUsuario).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Senha provisória"), "-provisoria");
    await userEvent.click(cadastrar);
    expect(api.liberarUsuario).toHaveBeenCalledWith("ana@grupocriterio.com.br", 1, "curta-provisoria");
    expect(await screen.findByRole("status")).toHaveTextContent("Passe a senha provisória para a pessoa");
    expect(screen.getByLabelText("Senha provisória")).toHaveValue("");
  });

  it("o perfil continua escolhível no cadastro", async () => {
    vi.mocked(api.liberarUsuario).mockResolvedValue({ ...PESSOAS[1], id: 3, email: "ana@grupocriterio.com.br" });
    comSenha();
    await userEvent.type(await screen.findByLabelText("E-mail da pessoa"), "ana@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha provisória"), "provisoria-1");
    fireEvent.change(screen.getByLabelText("Perfil da pessoa"), { target: { value: "2" } });
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
    expect(api.liberarUsuario).toHaveBeenCalledWith("ana@grupocriterio.com.br", 2, "provisoria-1");
  });

  it("redefine a senha de uma pessoa", async () => {
    vi.mocked(api.redefinirSenha).mockResolvedValue(undefined);
    comSenha();
    await userEvent.click(await screen.findByRole("button", { name: "Redefinir senha de karine@grupocriterio.com.br" }));
    const campo = screen.getByLabelText("Nova senha provisória de karine@grupocriterio.com.br");
    await userEvent.type(campo, "1234567");
    await userEvent.click(screen.getByRole("button", { name: "Salvar senha" }));
    expect(screen.getByRole("alert")).toHaveTextContent("pelo menos 8 caracteres");
    expect(api.redefinirSenha).not.toHaveBeenCalled();

    await userEvent.type(campo, "8{enter}");
    expect(api.redefinirSenha).toHaveBeenCalledWith(2, "12345678");
    expect(await screen.findByRole("status")).toHaveTextContent("Senha de karine@grupocriterio.com.br redefinida.");
    expect(screen.queryByLabelText("Nova senha provisória de karine@grupocriterio.com.br")).toBeNull();
  });

  it("no modo Microsoft não há senha na tela", async () => {
    render(<ProvedorDeAcesso eu={{ ...ADMIN_EU, modo: "microsoft" }}><PerfisEAcesso /></ProvedorDeAcesso>);
    expect(await screen.findByRole("columnheader", { name: "Conta Microsoft" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Senha provisória")).toBeNull();
    expect(screen.queryByRole("button", { name: /Redefinir senha/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Liberar acesso" })).toBeInTheDocument();
  });
});

const ALTERACOES: Alteracao[] = [
  { id: 9, quando: "2026-10-02T14:30:00", usuario_email: "karine@grupocriterio.com.br", usuario_nome: "Karine Nascimento",
    acao: "alterou", tabela: "oportunidade", registro_id: 5, descricao: "Alfa BPO", campo: "nome", antes: "Alfa BPO", depois: "Alfa BPO Full" },
  { id: 8, quando: "2026-10-02T14:00:00", usuario_email: "eduardo@grupocriterio.com.br", usuario_nome: null,
    acao: "criou", tabela: "pessoa_contato", registro_id: 3, descricao: "Ana Souza", campo: null, antes: null, depois: null },
];

describe("Histórico de alterações", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.usuarios).mockResolvedValue(PESSOAS);
    vi.mocked(api.historico).mockResolvedValue(ALTERACOES);
  });

  it("mostra quem, o quê, o campo e o antes → depois, e filtra por pessoa", async () => {
    render(<HistoricoDeAlteracoes />);
    const linha = (await screen.findByText("Karine Nascimento")).closest("tr")!;
    expect(linha).toHaveTextContent("Oportunidade");
    expect(linha).toHaveTextContent("nome");
    expect(linha).toHaveTextContent("Alfa BPO → Alfa BPO Full");
    const criou = screen.getByText("eduardo@grupocriterio.com.br").closest("tr")!;
    expect(criou).toHaveTextContent("Contato");
    expect(criou).toHaveTextContent("registro criado");

    await screen.findByRole("option", { name: "karine@grupocriterio.com.br" }); // sem nome ainda: aparece a conta
    fireEvent.change(screen.getByLabelText("Pessoa"), { target: { value: "karine@grupocriterio.com.br" } });
    await waitFor(() => expect(api.historico).toHaveBeenLastCalledWith(expect.objectContaining({ usuario: "karine@grupocriterio.com.br" })));
  });

  it("no painel do registro, só busca quando alguém abre", async () => {
    render(<AlteracoesDoRegistro tabela="contrato" id={4} />);
    expect(api.historico).not.toHaveBeenCalled();
    const recolhido = screen.getByText("Histórico de alterações").closest("details")!;
    recolhido.open = true;
    fireEvent(recolhido, new Event("toggle"));
    await waitFor(() => expect(api.historico).toHaveBeenCalledWith({ tabela: "contrato", registro_id: 4 }));
  });
});

describe("ações travadas pelo perfil", () => {
  const COMERCIAL_EU: Eu = {
    modo: "microsoft", email: "karine@grupocriterio.com.br", nome: "Karine", perfil: "Comercial", administrador: false,
    permissoes: ["contatos.ver", "contatos.editar"],
  };

  it("sem 'excluir' no perfil, o painel do contato diz o porquê em vez do botão", () => {
    render(
      <ProvedorDeAcesso eu={COMERCIAL_EU}>
        <DetalheDaPessoa pessoa={{ id: 3, nome: "Ana Souza", empresas: [] } as never} listas={null} aoFechar={vi.fn()} aoMudar={vi.fn()} />
      </ProvedorDeAcesso>,
    );
    expect(screen.queryByRole("button", { name: "Excluir contato" })).toBeNull();
    expect(screen.getByText(SEM_PERMISSAO)).toBeInTheDocument();
  });
});

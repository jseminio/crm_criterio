"""Sugestão de fusão: acha o que os dados reais mostram e não inventa parentesco."""

from __future__ import annotations

from dataclasses import dataclass

from crm.domain.sugestoes_de_fusao import chave_do_nome, sugerir, sugerir_clientes


@dataclass
class G:
    id: int
    nome: str
    quantas_oportunidades: int = 1


def _nomes(sug):
    return [sorted(s.ids) for s in sug]


def test_chave_ignora_acento_caixa_parenteses_e_o_que_vem_depois_do_traco():
    assert chave_do_nome("Sete Brasil (Leo Fraga) - BPO Contábil") == "sete brasil"
    assert chave_do_nome("Mainô - Revisão Term sheet") == chave_do_nome("Maino") == "maino"
    assert chave_do_nome("Rádio Tupi (Transação Individual)") == "radio tupi"
    assert chave_do_nome("Pedreira Araguaia Ltda - Transação Tributária") == "pedreira araguaia"


def test_mesma_chave_vira_um_bloco_de_alta_confianca():
    s = sugerir([G(1, "Sete Brasil (Leo Fraga) - BPO"), G(2, "Sete Brasil (Leo Fraga) - Bacen"), G(3, "Outro")])
    assert _nomes(s) == [[1, 2]] and s[0].confianca == "alta"


def test_nome_contido_com_duas_palavras_e_media():
    s = sugerir([G(1, "Andréa Curcio"), G(2, "BPO Contábil Andréa Curcio")])
    assert s[0].confianca == "média" and sorted(s[0].ids) == [1, 2]


def test_uma_palavra_dentro_de_outro_nome_nao_e_sugerida():
    assert sugerir([G(1, "Aeskins"), G(2, "Horas adicionais Aeskins")]) == []


def test_nomes_so_parecidos_na_escrita_nao_sao_sugeridos():
    assert sugerir([G(1, "BRA (Leo Fraga)"), G(2, "BRAP (Leo Fraga)")]) == []


def test_principal_e_o_grupo_com_mais_propostas():
    s = sugerir([G(1, "Alfa - a", 1), G(2, "Alfa - b", 5), G(3, "Alfa - c", 2)])
    assert s[0].principal_id == 2


def test_sem_parecidos_nao_devolve_nada():
    assert sugerir([G(1, "Alfa"), G(2, "Beta")]) == []


def test_ligacao_media_nao_encadeia_nomes_sem_relacao():
    """Regressão: "joao silva" e "silva santos" estão ambos dentro de "joao silva
    santos", mas não um no outro. Antes caíam num bloco só, e um clique fundia os três."""
    s = sugerir([G(1, "João Silva"), G(2, "Silva Santos"), G(3, "João Silva Santos")])
    assert _nomes(s) == [[1, 3], [2, 3]]
    assert all(x.confianca == "média" for x in s)
    assert not any({1, 2} <= set(x.ids) for x in s)


def test_nome_generico_dentro_de_varios_clientes_nao_os_junta():
    s = sugerir([G(1, "BPO Contábil"), G(2, "BPO Contábil Andréa Curcio"), G(3, "BPO Contábil Sete Brasil")])
    assert _nomes(s) == [[1, 2], [1, 3]]
    assert not any({2, 3} <= set(x.ids) for x in s)


def test_par_medio_leva_todos_os_grupos_de_cada_nome():
    s = sugerir([G(1, "Andréa Curcio"), G(2, "BPO Contábil Andréa Curcio - A"), G(3, "BPO Contábil Andréa Curcio - B")])
    alta = [x for x in s if x.confianca == "alta"]
    media = [x for x in s if x.confianca == "média"]
    assert _nomes(alta) == [[2, 3]]
    assert _nomes(media) == [[1, 2, 3]]
    assert media[0].motivo == "Um nome contém o outro: andrea curcio ⊂ bpo contabil andrea curcio."


@dataclass
class GE:
    id: int
    nome: str
    quantas_oportunidades: int = 0
    empresas: list[str] = None

    def __post_init__(self):
        self.empresas = self.empresas or []


class TestProspectQueJaECliente:
    def test_acha_pela_palavra_em_comum_com_o_nome_do_grupo(self):
        s = sugerir_clientes([GE(10, "ASM retomada pelo Antonio - 3AW")], [GE(1, "Grupo 3AW", empresas=["3AW BRASIL PROPAGANDA S.A."])])
        assert len(s) == 1 and s[0].ids == [1, 10] and s[0].principal_id == 1 and "3aw" in s[0].motivo and "no nome do grupo" in s[0].motivo

    def test_acha_pelo_nome_de_uma_das_empresas_do_grupo(self):
        s = sugerir_clientes([GE(10, "Cedae Saúde")], [GE(1, "Grupo Inbel", empresas=["CEDAE SAUDE ASSISTENCIA LTDA", "INBEL SA"])])
        assert [x.ids for x in s] == [[1, 10]]
        assert "na empresa CEDAE SAUDE ASSISTENCIA LTDA" in s[0].motivo   # diz onde a palavra apareceu

    def test_palavra_generica_nao_liga_ninguem(self):
        assert sugerir_clientes([GE(10, "GI Gestão")], [GE(1, "F102 Consultoria e Gestão")]) == []

    def test_palavra_que_aponta_para_dois_clientes_e_ambigua_e_nao_sugere(self):
        clientes = [GE(1, "Alfa Delta"), GE(2, "Beta Delta")]
        assert sugerir_clientes([GE(10, "Delta Prospect")], clientes) == []

    def test_prospect_que_aponta_para_dois_clientes_diferentes_e_ignorado(self):
        clientes = [GE(1, "Grupo Voa"), GE(2, "Grupo Sunsto")]
        assert sugerir_clientes([GE(10, "Voa Sunsto Tech")], clientes) == []

    def test_cada_sugestao_e_um_par_com_o_cliente_como_principal(self):
        s = sugerir_clientes([GE(10, "Voa Sales Tech"), GE(11, "Holding Duda - VOA")], [GE(1, "Grupo Voa")])
        assert [(x.ids, x.principal_id) for x in s] == [([1, 10], 1), ([1, 11], 1)]

    def test_sem_parecido_nao_devolve_nada(self):
        assert sugerir_clientes([GE(10, "Zeta")], [GE(1, "Grupo Alfa")]) == []


def test_api_sugere_tambem_o_cliente_nao_recorrente_que_duplica_um_da_carteira(engine, sessao):
    """Depois que a proposta aceita torna o grupo Cliente, o duplicado não pode sumir das sugestões."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from crm.api.app import criar_app
    from crm.db.modelos import Empresa, GrupoEconomico
    from crm.domain.listas import SituacaoGrupo

    carteira = GrupoEconomico(nome="Grupo 3AW", situacao=SituacaoGrupo.CLIENTE)
    pontual = GrupoEconomico(nome="ASM retomada pelo Antonio - 3AW", situacao=SituacaoGrupo.CLIENTE)  # aceita, sem empresa
    outro = GrupoEconomico(nome="Zeta Qualquer", situacao=SituacaoGrupo.CLIENTE)
    sessao.add_all([carteira, pontual, outro]); sessao.flush()
    sessao.add(Empresa(grupo_id=carteira.id, razao_social="3AW BRASIL PROPAGANDA S.A.", cnpj="11222333000181"))
    sessao.commit()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        s = c.get("/api/grupos/sugestoes-de-fusao").json()
    pares = [{g["id"] for g in x["grupos"]} for x in s]
    assert {carteira.id, pontual.id} in pares and all(outro.id not in p for p in pares)
    assert next(x for x in s if {g["id"] for g in x["grupos"]} == {carteira.id, pontual.id})["principal_id"] == carteira.id

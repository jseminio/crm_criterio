"""Sugestão de fusão: acha o que os dados reais mostram e não inventa parentesco."""

from __future__ import annotations

from dataclasses import dataclass

from crm.domain.sugestoes_de_fusao import chave_do_nome, sugerir


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

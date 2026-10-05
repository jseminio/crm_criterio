"""A regra do dono (#93): nada manual no servidor. Estes testes a obrigam.

(a) toda variável lida no código (src/, scripts/, *.sh do container) está no catálogo `crm.config`;
(b) toda variável do catálogo está no `.env.example` e no `docker-compose.coolify.yml`, coerente;
(c)/(d) estão em `tests/test_manutencao.py`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from crm.config import CATALOGO, ONDE_CONFIGURAR, POR_NOME, conferir

BACKEND = Path(__file__).resolve().parent.parent
RAIZ = BACKEND.parent.parent
NOME = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
PREFIXOS = ("CRM_", "ANTHROPIC_")


def _lidas_no_python() -> dict[str, str]:
    """Nome → onde. Pega `os.environ[...]`, `os.environ.get(...)`, `os.getenv(...)`, `x.get("NOME")`
    e toda constante "CRM_…"/"ANTHROPIC_…" (as que o código lê por um dicionário de nomes)."""
    achadas: dict[str, str] = {}
    for pasta in (BACKEND / "src", BACKEND / "scripts", BACKEND / "migrations"):
        for arquivo in pasta.rglob("*.py"):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                texto = None
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr in ("get", "getenv"):
                    if no.args and isinstance(no.args[0], ast.Constant) and isinstance(no.args[0].value, str):
                        texto = no.args[0].value
                elif isinstance(no, ast.Subscript) and "environ" in ast.unparse(no.value):
                    if isinstance(no.slice, ast.Constant) and isinstance(no.slice.value, str):
                        texto = no.slice.value
                elif isinstance(no, ast.Constant) and isinstance(no.value, str) and no.value.startswith(PREFIXOS):
                    texto = no.value
                if texto and NOME.match(texto):
                    achadas.setdefault(texto, f"{arquivo.relative_to(BACKEND)}:{getattr(no, 'lineno', '?')}")
    return achadas


def _lidas_nos_sh() -> dict[str, str]:
    achadas: dict[str, str] = {}
    for arquivo in (BACKEND / "atualizador.sh", BACKEND / "entrypoint.sh"):
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            for nome in re.findall(r"\$\{([A-Z][A-Z0-9_]+):?[-?=]", linha):
                achadas.setdefault(nome, f"{arquivo.name}:{n}")
    return achadas


def test_a_toda_variavel_lida_no_codigo_esta_no_catalogo():
    lidas = {**_lidas_no_python(), **_lidas_nos_sh()}
    fora = {nome: onde for nome, onde in lidas.items() if nome not in POR_NOME}
    assert not fora, (f"variável lida no código e fora do catálogo crm/config.py: {fora}. "
                      "Catalogue-a com padrão seguro, no .env.example e no docker-compose.coolify.yml.")
    # A varredura enxerga de fato o que existe hoje (senão o teste passaria vazio).
    assert {"CRM_DATABASE_URL", "CRM_SEGREDO_SESSAO", "ANTHROPIC_API_KEY", "STRICT_UPDATER"} <= set(lidas)


def test_catalogo_sem_nome_repetido():
    nomes = [v.nome for v in CATALOGO]
    assert len(nomes) == len(set(nomes))


def _env_example() -> set[str]:
    texto = (BACKEND / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", texto, re.MULTILINE))


def _compose_da_api() -> dict[str, str]:
    """As linhas `NOME: valor` do bloco environment do crmcs-api no compose do Coolify."""
    texto = (RAIZ / "docker-compose.coolify.yml").read_text(encoding="utf-8")
    bloco = texto.split("  crmcs-api:", 1)[1].split("\n  crmcs-web:", 1)[0]
    env = bloco.split("    environment:", 1)[1].split("\n    expose:", 1)[0]
    return dict(re.findall(r"^\s{6}([A-Z][A-Z0-9_]+):\s*(.*?)\s*$", env, re.MULTILINE))


def test_b_toda_variavel_do_catalogo_esta_no_env_example():
    faltam = [v.nome for v in CATALOGO if v.nome not in _env_example()]
    assert not faltam, f"no catálogo e fora do app/backend/.env.example: {faltam}"


@pytest.mark.parametrize("v", CATALOGO, ids=lambda v: v.nome)
def test_b_compose_do_coolify_coerente_com_o_catalogo(v):
    compose = _compose_da_api()
    if v.origem == "local":
        assert v.nome not in compose, f"{v.nome} é só do desenvolvimento local e não vai para o container"
        return
    assert v.nome in compose, f"{v.nome} está no catálogo e falta no docker-compose.coolify.yml"
    valor = compose[v.nome].strip('"')
    if v.origem == "fixa":
        assert valor == v.valor_fixo
    elif v.obrigatoria:
        assert valor.startswith(f"${{{v.nome}:?") and ONDE_CONFIGURAR.split(" em ")[1] in valor, valor
    else:
        m = re.fullmatch(rf"\$\{{{v.nome}:-(.*)\}}", valor)
        assert m, f"{v.nome}: opcional precisa de ${{{v.nome}:-padrão}}, achei {valor}"
        # Vazio = o código aplica o próprio padrão; senão, o mesmo padrão do catálogo.
        assert m.group(1) in ("", v.padrao), f"{v.nome}: padrão do compose ({m.group(1)}) ≠ catálogo ({v.padrao})"


def test_padroes_do_catalogo_iguais_aos_do_codigo():
    from crm.agente.sdr import MODELO_PADRAO
    from crm.db.sessao import PADROES, PARTES

    assert POR_NOME["CRM_AGENTE_MODELO"].padrao == MODELO_PADRAO
    for parte, padrao in PADROES.items():
        assert POR_NOME[PARTES[parte]].padrao == padrao
    sys.path.insert(0, str(BACKEND / "scripts"))
    import servir_producao as sp

    assert sp.parametros({"CRM_ADMIN_EMAIL": "a@b.c", "CRM_SEGREDO_SESSAO": "x" * 32,
                          "CRM_ADMIN_SENHA_INICIAL": "12345678"})["port"] == 8000


VALIDO = {"CRM_DATABASE_URL": "postgres://u:SENHA-DO-BANCO-9@h:5432/db", "CRM_SEGREDO_SESSAO": "S" * 40,
          "CRM_ADMIN_EMAIL": "admin@exemplo.com.br", "CRM_ADMIN_SENHA_INICIAL": "SENHA-INICIAL-7"}


def test_ambiente_completo_diz_nada_a_fazer():
    r = conferir(VALIDO)
    assert r.ok and r.linhas()[-1] == "ambiente em dia: nada a fazer."
    assert any("CRM_AGENTE_MODELO ausente: usa o padrão" in linha for linha in r.linhas())


@pytest.mark.parametrize("falta", ["CRM_SEGREDO_SESSAO", "CRM_DATABASE_URL", "CRM_ADMIN_EMAIL", "CRM_ADMIN_SENHA_INICIAL"])
def test_obrigatoria_ausente_aborta_dizendo_qual_e_onde(falta):
    r = conferir({k: v for k, v in VALIDO.items() if k != falta})
    assert not r.ok
    assert any(falta in e and "Coolify › crmcs › Environment Variables" in e for e in r.erros)


def test_url_pelas_partes_satisfaz_a_obrigatoria():
    valores = {k: v for k, v in VALIDO.items() if k != "CRM_DATABASE_URL"}
    valores |= {"CRM_DB_HOST": "h", "CRM_DB_USER": "u", "CRM_DB_PASSWORD": "p"}
    assert conferir(valores).ok


def test_nunca_imprime_valor_de_segredo(capsys):
    sys.path.insert(0, str(BACKEND / "scripts"))
    import conferir_ambiente

    ruins = VALIDO | {"CRM_SEGREDO_SESSAO": "CURTO-SECRETO", "CRM_M365_CLIENT_SECRET": "M365-SECRETO-1",
                      "CRM_QUESTIONARIO_CHAVE": "CHAVE-SECRETA-2", "BACKUP_ANTES_DIAS": "zero"}
    assert conferir_ambiente.main(ruins) == 1
    saida = capsys.readouterr()
    tudo = saida.out + saida.err
    for segredo in ("CURTO-SECRETO", "M365-SECRETO-1", "CHAVE-SECRETA-2", "SENHA-DO-BANCO-9", "SENHA-INICIAL-7"):
        assert segredo not in tudo
    assert "CRM_SEGREDO_SESSAO precisa de pelo menos 32" in tudo
    assert "BACKUP_ANTES_DIAS" in tudo and "CRM_M365_TENANT_ID" in tudo  # grupo incompleto avisado


# --- Backup antes da migração (pg_dump falso: nenhum banco real) ----------------------------------

def _falso(pasta: Path, nome: str, corpo: str) -> None:
    caminho = pasta / nome
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)


@pytest.fixture
def binarios(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    registro = tmp_path / "argv.txt"
    _falso(bin_, "pg_dump", f'echo "$@ PGPASSWORD=$PGPASSWORD" >> {registro}\n'
           'while [ "$1" != "-f" ]; do shift; done; echo dump > "$2"\n')
    _falso(bin_, "pg_restore", "exit 0\n")
    monkeypatch.setenv("PATH", f"{bin_}:{__import__('os').environ['PATH']}")
    return bin_, registro


def test_backup_senha_fora_do_argv_e_retencao(tmp_path, binarios):
    from datetime import datetime, timedelta, timezone

    from crm.backup.antes_da_migracao import PREFIXO, fazer_backup

    _, registro = binarios
    pasta = tmp_path / "backups"
    url = "postgresql+psycopg://crmcs:s%23nh%40@db:5432/crmcs"
    inicio = datetime(2026, 10, 5, tzinfo=timezone.utc)
    for i in range(4):
        fazer_backup(url, pasta=pasta, de="a1", para="b2", dias=7, agora=inicio + timedelta(seconds=i))
    guardados = sorted(p.name for p in pasta.glob(f"{PREFIXO}*.dump"))
    assert len(guardados) == 4 and guardados[-1].endswith("000003-a1-para-b2.dump")  # todos de hoje: ficam
    argv = registro.read_text().splitlines()[0]
    assert "s#nh@" not in argv.split(" PGPASSWORD=")[0] and argv.endswith("PGPASSWORD=s#nh@")
    assert "postgresql://crmcs@db:5432/crmcs" in argv


def test_backup_que_falha_nao_deixa_parcial_nem_apaga(tmp_path, binarios):
    from crm.backup.antes_da_migracao import BackupFalhou, PREFIXO, fazer_backup

    bin_, _ = binarios
    pasta = tmp_path / "backups"
    pasta.mkdir()
    (pasta / f"{PREFIXO}antigo.dump").write_text("x")
    _falso(bin_, "pg_dump", 'echo "server version mismatch; server version: 18.0; pg_dump version: 17.6" >&2; exit 1\n')
    with pytest.raises(BackupFalhou, match="server version mismatch"):
        fazer_backup("postgres://u:p@h/db", pasta=pasta, de="", para="b2", dias=1)
    assert [p.name for p in pasta.iterdir()] == [f"{PREFIXO}antigo.dump"]


# --- Retenção por idade (BACKUP_ANTES_DIAS) ---------------------------------------------------------

def _dump_com_idade(pasta: Path, nome: str, dias: float, agora) -> Path:
    import os

    caminho = pasta / nome
    caminho.write_text("dump")
    momento = agora.timestamp() - dias * 86400
    os.utime(caminho, (momento, momento))
    return caminho


def test_retencao_apaga_so_o_mais_velho_que_o_prazo(tmp_path):
    from datetime import datetime, timezone

    from crm.backup.antes_da_migracao import PREFIXO, aplicar_retencao

    agora = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    velho = _dump_com_idade(tmp_path, f"{PREFIXO}oito.dump", 8, agora)
    novo = _dump_com_idade(tmp_path, f"{PREFIXO}dois.dump", 2, agora)
    assert aplicar_retencao(tmp_path, 7, agora=agora) == [velho]
    assert not velho.exists() and novo.exists()


def test_retencao_nunca_zera_a_pasta(tmp_path):
    from datetime import datetime, timezone

    from crm.backup.antes_da_migracao import PREFIXO, aplicar_retencao

    agora = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    unico = _dump_com_idade(tmp_path, f"{PREFIXO}trinta.dump", 30, agora)
    assert aplicar_retencao(tmp_path, 7, agora=agora) == []
    assert unico.exists()


def test_retencao_preserva_o_recem_criado_mesmo_velho(tmp_path):
    from datetime import datetime, timezone

    from crm.backup.antes_da_migracao import PREFIXO, aplicar_retencao

    agora = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    recente = _dump_com_idade(tmp_path, f"{PREFIXO}dez.dump", 10, agora)
    protegido = _dump_com_idade(tmp_path, f"{PREFIXO}vinte.dump", 20, agora)
    assert aplicar_retencao(tmp_path, 7, protegido=protegido, agora=agora) == []
    assert recente.exists() and protegido.exists()


def test_retencao_nao_toca_em_arquivo_de_outro_prefixo(tmp_path):
    from datetime import datetime, timezone

    from crm.backup.antes_da_migracao import PREFIXO, aplicar_retencao

    agora = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    alheios = [_dump_com_idade(tmp_path, nome, 90, agora)
               for nome in ("crmcs-diario-20260601.dump", "outro.dump", f"{PREFIXO}velho.dump.parcial")]
    _dump_com_idade(tmp_path, f"{PREFIXO}novo.dump", 1, agora)
    assert aplicar_retencao(tmp_path, 7, agora=agora) == []
    assert all(p.exists() for p in alheios)


@pytest.mark.parametrize("dias", ["0", "-1", "sete", ""])
def test_dias_invalido_sai_com_erro_sem_tocar_no_banco(dias, capsys):
    from crm.backup.antes_da_migracao import main

    assert main(["--dias", dias, "--pasta", "/nao/existe"]) == 1
    assert "BACKUP_ANTES_DIAS precisa ser" in capsys.readouterr().err

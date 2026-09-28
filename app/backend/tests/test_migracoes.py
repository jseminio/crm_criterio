"""As migrações terminam numa ponta só.

Em 27/09/2026 duas branches criaram migrações a partir do mesmo ponto e a
`main` ficou com duas pontas: `alembic upgrade head` recusou rodar na máquina
de Eduardo. Este teste pega isso antes do merge, sem precisar de banco.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parent.parent


def test_uma_ponta_so():
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    pontas = ScriptDirectory.from_config(config).get_heads()
    assert len(pontas) == 1, f"mais de uma ponta de migração: {pontas}. Crie uma junção com `alembic merge`."

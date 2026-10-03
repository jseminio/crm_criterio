"""Apaga um grupo de teste inteiro, com tudo o que é dele (03/10/2026, pedido de Eduardo).

    apagar_grupo.py --cnpj 66108756000167            só mostra o que seria apagado
    apagar_grupo.py --cnpj 66108756000167 --apagar   mostra e apaga

Para o que entrou por teste (o "Karine ON", com o CNPJ da Salus). O grupo vem pelo CNPJ de uma empresa
dele ou pelo nome exato (`--grupo`). Sai, numa transação só: o grupo, as empresas, as oportunidades (com
proposta, pendências, histórico de preço e questionários), os vínculos, os contatos que só existem
nele, a leitura do Score, a jornada, as reuniões e os ajustes. O histórico de alterações fica, porque
é o registro do que aconteceu.

Recusa quando o grupo tem **contrato** (apagar quebraria o MRR e a carteira) ou entrou numa fusão:
isso se resolve na tela. Sem `--apagar`, nada é gravado. Com `--apagar`, apaga sem backup antes
(Eduardo dispensou o backup em 03/10/2026, para o grupo de teste); para guardar, rode antes
`backup.py exportar`.

⚠️ A saída tem nomes: fica na tela.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from crm.db.modelos import (  # noqa: E402
    AjusteTecnico, ClassificacaoDoGrupo, Contrato, Empresa, FusaoDeGrupos, GrupoEconomico, HistoricoDePreco,
    JornadaDoCliente, Lead, Oportunidade, OportunidadeDaReuniao, PendenciaDaProposta, PessoaContato, Proposta,
    QuestionarioRecebido, ReuniaoDeResultado, VinculoDeContato,
)
from crm.db.sessao import criar_engine  # noqa: E402

class Recusado(Exception):
    pass


def _grupo(s: Session, cnpj: str | None, nome: str | None) -> GrupoEconomico:
    if cnpj:
        digitos = "".join(c for c in cnpj if c.isdigit())
        empresas = [e for e in s.scalars(sa.select(Empresa).where(Empresa.cnpj.is_not(None)))
                    if "".join(c for c in e.cnpj if c.isdigit()).zfill(14) == digitos.zfill(14)]
        if len(empresas) != 1:
            raise Recusado(f"Achei {len(empresas)} empresas com o CNPJ {cnpj}; preciso de exatamente uma.")
        return s.get(GrupoEconomico, empresas[0].grupo_id)
    grupos = list(s.scalars(sa.select(GrupoEconomico).where(sa.func.lower(GrupoEconomico.nome) == (nome or "").lower())))
    if len(grupos) != 1:
        raise Recusado(f"Achei {len(grupos)} grupos com o nome {nome!r}; preciso de exatamente um.")
    return grupos[0]


def plano(s: Session, g: GrupoEconomico) -> dict[str, list]:
    """Tudo o que sai com o grupo, por tabela, na ordem em que se apaga (quem aponta, antes)."""
    if s.scalar(sa.select(Contrato.id).where(Contrato.grupo_id == g.id).limit(1)) is not None:
        raise Recusado(f"O grupo {g.nome!r} tem contrato: encerre ou mova o contrato na tela antes.")
    if g.fundido_em_id is not None or s.scalar(sa.select(FusaoDeGrupos.id).where(
            (FusaoDeGrupos.principal_id == g.id) | (FusaoDeGrupos.absorvido_id == g.id)).limit(1)) is not None:
        raise Recusado(f"O grupo {g.nome!r} entrou numa fusão: desfaça a fusão na tela antes.")
    if s.scalar(sa.select(GrupoEconomico.id).where(GrupoEconomico.fundido_em_id == g.id).limit(1)) is not None:
        raise Recusado(f"Outro grupo foi fundido em {g.nome!r}: desfaça a fusão na tela antes.")
    empresas = list(s.scalars(sa.select(Empresa).where(Empresa.grupo_id == g.id)))
    ids_emp = [e.id for e in empresas]
    oportunidades = list(s.scalars(sa.select(Oportunidade).where(Oportunidade.grupo_id == g.id)))
    ids_op = [o.id for o in oportunidades]
    if ids_op and s.scalar(sa.select(Contrato.id).where(Contrato.oportunidade_id.in_(ids_op)).limit(1)) is not None:
        raise Recusado("Uma oportunidade do grupo virou contrato: resolva o contrato na tela antes.")
    vinculos = list(s.scalars(sa.select(VinculoDeContato).where(VinculoDeContato.empresa_id.in_(ids_emp)))) if ids_emp else []
    # O contato sai só se não tiver vínculo com empresa de outro grupo.
    pessoas = []
    for pid in sorted({v.pessoa_id for v in vinculos}):
        fora = s.scalar(sa.select(VinculoDeContato.id).where(
            VinculoDeContato.pessoa_id == pid, VinculoDeContato.empresa_id.not_in(ids_emp)).limit(1))
        if fora is None:
            pessoas.append(s.get(PessoaContato, pid))
    reunioes = list(s.scalars(sa.select(ReuniaoDeResultado).where(ReuniaoDeResultado.grupo_id == g.id)))
    questionarios = list(s.scalars(sa.select(QuestionarioRecebido).where(
        (QuestionarioRecebido.grupo_id == g.id)
        | (QuestionarioRecebido.oportunidade_id.in_(ids_op or [-1]))
        | (QuestionarioRecebido.oportunidade_em_aberto_id.in_(ids_op or [-1])))))
    por_op = lambda modelo: list(s.scalars(sa.select(modelo).where(modelo.oportunidade_id.in_(ids_op)))) if ids_op else []  # noqa: E731
    return {
        "questionário recebido": questionarios,
        "venda anotada em reunião": list(s.scalars(sa.select(OportunidadeDaReuniao).where(
            (OportunidadeDaReuniao.grupo_id == g.id) | (OportunidadeDaReuniao.oportunidade_id.in_(ids_op or [-1]))))),
        "ajuste da área técnica": list(s.scalars(sa.select(AjusteTecnico).where(AjusteTecnico.grupo_id == g.id))),
        "reunião de resultado": reunioes,
        "pendência da proposta": por_op(PendenciaDaProposta),
        "proposta": por_op(Proposta),
        "histórico de preço": por_op(HistoricoDePreco),
        "oportunidade": oportunidades,
        "vínculo de contato": vinculos,
        "contato": pessoas,
        "empresa": empresas,
        "leitura do Score": list(s.scalars(sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == g.id))),
        "jornada do cliente": list(s.scalars(sa.select(JornadaDoCliente).where(JornadaDoCliente.grupo_id == g.id))),
        "grupo": [g],
    }


def _nome(x) -> str:
    for campo in ("nome", "razao_social", "descricao", "lacuna", "chave", "tipo"):
        v = getattr(x, campo, None)
        if v:
            extra = f" · {x.cnpj}" if getattr(x, "cnpj", None) else (f" · {x.email}" if getattr(x, "email", None) else "")
            return f"{v}{extra}"
    if isinstance(x, Proposta):
        return f"proposta {x.numero}/{x.ano}"
    return f"#{getattr(x, 'id', '?')}"


def apagar(s: Session, itens: dict[str, list]) -> None:
    ids_op = [o.id for o in itens["oportunidade"]]
    if ids_op:  # o lead continua; só deixa de apontar para a oportunidade que sai
        s.execute(sa.update(Lead).where(Lead.convertido_em_id.in_(ids_op)).values(convertido_em_id=None))
    for lista in itens.values():
        for x in lista:
            s.delete(x)
        s.flush()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    qual = p.add_mutually_exclusive_group(required=True)
    qual.add_argument("--cnpj")
    qual.add_argument("--grupo")
    p.add_argument("--apagar", action="store_true")
    a = p.parse_args()
    engine = criar_engine()
    with Session(engine) as s:
        try:
            g = _grupo(s, a.cnpj, a.grupo)
            itens = plano(s, g)
        except Recusado as motivo:
            print(f"✗ {motivo} Nada foi apagado.")
            return 1
        print(f"Grupo {g.nome!r} (situação {g.situacao.value if g.situacao else '—'}). Sairia:")
        for tabela, lista in itens.items():
            if lista:
                print(f"  • {tabela}: {len(lista)}")
                for x in lista[:20]:
                    print(f"      - {_nome(x)}")
        if not a.apagar:
            print("\nNada foi apagado. Para apagar, rode de novo com --apagar.")
            return 0
        apagar(s, itens)
        s.commit()
    print(f"✓ Grupo {g.nome!r} apagado, com tudo o que era dele.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

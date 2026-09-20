"""Roda a carga contra uma planilha real e imprime o relatório de conferência.

Uso:  .venv/bin/python scripts/conferir_carga.py <caminho da planilha>

Não grava nada: só lê e mostra. Os dados são de clientes da Critério.
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crm.carga.arquivo import ler_aba_propostas
from crm.carga.planilha_2026 import carregar

caminho = sys.argv[1]
propostas, rel = carregar(ler_aba_propostas(caminho))

print(rel.resumo())
print()
print(f"Completas (viram oportunidade): {sum(1 for p in propostas if p.completa)}")
print(f"Incompletas: {sum(1 for p in propostas if not p.completa)}")
print()
print("Distribuição por situação:")
for s, n in Counter(p.situacao.value for p in propostas if p.situacao).most_common():
    print(f"  {s}: {n}")
print()
print("Distribuição por tipo de canal:")
for c, n in Counter(p.tipo_canal.value for p in propostas if p.tipo_canal).most_common():
    print(f"  {c}: {n}")
print()
print("Distribuição por captador:")
for c, n in Counter(p.captador for p in propostas if p.captador).most_common():
    print(f"  {c}: {n}")
print()
bloqueios = [a for a in rel.avisos if a.bloqueia]
print(f"Pendências que impedem virar oportunidade: {len(bloqueios)}")
for a in bloqueios[:10]:
    print(f"  linha {a.linha} · {a.campo} · {a.texto}")

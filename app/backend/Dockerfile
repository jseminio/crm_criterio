# API do Critério CRM (crmcs) em container. Passo a passo em app/IMPLANTACAO.md, seção "Coolify".
#
# - UM processo só (scripts/servir_producao.py, uvicorn com workers=1): a busca automática dos
#   questionários roda dentro da API e o bloqueio de tentativas de senha vive na memória do processo.
#   Não troque por gunicorn com vários workers.
# - A API não grava nada em disco: matrizes de proposta, backup importado e arquivos gerados vivem no
#   banco ou na memória. Por isso não há volume.
# - Sem .env na imagem (o .dockerignore o tira): a configuração chega pelo ambiente do container.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo

# O driver é psycopg[binary] (traz a libpq): não precisa de gcc nem de libpq-dev.
# postgresql-client: pg_isready no entrypoint. curl: healthcheck. tzdata: TZ.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client curl tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home --home-dir /app --shell /usr/sbin/nologin appuser

WORKDIR /app

# Camada de dependências: só muda quando o pyproject.toml muda. A lista é a do próprio
# pyproject (project.dependencies), lida aqui, para não manter duas.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/dependencias.txt \
    && pip install -r /tmp/dependencias.txt \
    && rm /tmp/dependencias.txt

COPY . .
RUN pip install --no-deps -e . \
    && chmod 0755 entrypoint.sh atualizador.sh \
    && chown -R root:root /app \
    && chmod -R a+rX /app

# O código fica de root, só leitura para o appuser: o processo não consegue alterar a si mesmo.
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "scripts/servir_producao.py"]

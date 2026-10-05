# Tela do Critério CRM (crmcs): build com Node, servida por nginx sem root, que também repassa /api
# à API (serviço "backend" do compose). Passo a passo em app/IMPLANTACAO.md, seção "Coolify".

# ---------------------------------------------------------------- build
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------------------------------------------------------------- runner
FROM nginxinc/nginx-unprivileged:alpine

ENV TZ=America/Sao_Paulo

# tzdata para o horário do log; a imagem roda como o usuário nginx (uid 101), sem root.
USER root
RUN apk add --no-cache tzdata \
    && rm -f /etc/nginx/conf.d/*.conf
COPY nginx.conf /etc/nginx/conf.d/crmcs.conf
COPY --from=build /src/dist /usr/share/nginx/html
USER 101

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

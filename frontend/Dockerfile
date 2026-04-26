FROM node:20-alpine AS build
WORKDIR /app

# Cachebust — alterar este timestamp força rebuild quando o conteúdo do src muda
ARG CACHEBUST=2026-04-26-v12-cors-autodetect
RUN echo "Build cachebust: $CACHEBUST"

COPY package*.json ./
RUN npm install

COPY . .

# Verificação — falha o build se o client.ts antigo ainda lá estiver
RUN grep -q "resolveBase" src/api/client.ts || (echo "ERRO: client.ts não tem resolveBase — código antigo!" && exit 1)
RUN ! grep -q "VITE_API_BASE_URL || 'http://localhost:8001'" src/api/client.ts || (echo "ERRO: client.ts ainda tem código antigo!" && exit 1)

RUN npm run build

# Verificação pós-build — confirma que o bundle não tem '/api/' hardcoded
RUN ! grep -q '"/api/"' dist/assets/*.js || (echo "ERRO: bundle ainda contém /api/ — build velho!" && exit 1)

FROM nginx:1.27-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 10000

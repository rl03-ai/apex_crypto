# Apex Crypto

Trading dashboard para mercado crypto — scanner com scoring multi-factor, watchlist com alertas, gestão de portfolios com P&L, e enriquecimento via DefiLlama.

## Stack

- **Backend** — FastAPI · SQLAlchemy · APScheduler · Pydantic v2
- **Frontend** — React 18 · TypeScript · Vite · Recharts · React Router
- **Dados** — CoinGecko (preços, market cap, tokenomics) · DefiLlama (TVL) · Alternative.me (Fear & Greed)
- **Persistência** — SQLite (dev) ou PostgreSQL (produção)

## Funcionalidades

- **Scanner** com score composto em 6 dimensões: adoption, quality, valuation, market, catalysts, risk
- **Watchlist** com alertas de preço acima/abaixo e score acima
- **Portfolio** com posições, lots, refresh de preços live e P&L
- **Alertas automáticos** a cada 10 min para watchlist, 15 min para P&L de portfolios
- **Página de detalhe** por moeda com tokenomics, ATH/ATL, TVL (DefiLlama), comunidade
- **Fear & Greed Index** integrado no dashboard

## Estrutura

```
apex_crypto/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── core/            # config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── api/routes/      # endpoints
│   │   ├── services/        # CoinGecko, DefiLlama, scoring, cache
│   │   └── jobs/            # scheduler + jobs (alerts, portfolio update, cleanup)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # React SPA
│   ├── src/
│   │   ├── api/             # client + endpoints tipados
│   │   ├── components/      # Layout, CryptoTable, FearGreedGauge, etc.
│   │   ├── pages/           # Dashboard, Asset, Watchlist, Portfolio, Alerts, Login
│   │   └── types/           # TypeScript types
│   ├── nginx/               # config para serving em Docker
│   └── Dockerfile
├── docker-compose.yml       # stack local completa com Postgres
├── render.yaml              # deploy Render.com (API + frontend + DB)
└── README.md
```

## Desenvolvimento local

### Opção 1 — sem Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8001 --reload
```

A API arranca em `http://localhost:8001` com Swagger em `/docs`.

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

A aplicação fica em `http://localhost:5173`. Ao abrir, és redireccionado para `/login` — cria uma conta e segue para o scanner.

### Opção 2 — Docker Compose (com Postgres)

```bash
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend (directo): `http://localhost:8001`
- Postgres: `localhost:5432` (user: `apex`, password: `apex`, db: `apex_crypto`)

O frontend faz proxy para o backend via `/api/` (configurado no nginx) — não precisas de tocar em `VITE_API_BASE_URL` neste setup.

## Variáveis de ambiente — Backend

| Variável | Default | Descrição |
|---|---|---|
| `APP_NAME` | `Apex Crypto API` | Título mostrado no Swagger |
| `DEBUG` | `true` | Em `false` exige sempre JWT (produção) |
| `SECRET_KEY` | `change-me-in-production` | **OBRIGATÓRIO em produção** — usa `openssl rand -hex 32` |
| `DATABASE_URL` | `sqlite:///./apex_crypto.db` | Postgres: `postgresql://user:pwd@host:5432/db` |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:5174` | Lista CSV de origens permitidas |
| `COINGECKO_BASE_URL` | `https://api.coingecko.com/api/v3` | Endpoint público da CoinGecko |
| `COINGECKO_API_KEY` | _(vazio)_ | Chave Pro opcional para evitar rate limits |
| `DEFILLAMA_BASE_URL` | `https://api.llama.fi` | Endpoint público |
| `SCHEDULER_ENABLED` | `true` | Pôr `false` para desactivar todos os jobs |
| `ALERT_CHECK_INTERVAL_MINUTES` | `10` | Frequência da verificação de alertas |
| `PORTFOLIO_UPDATE_INTERVAL_MINUTES` | `15` | Frequência do refresh de preços de portfolios |

## Variáveis de ambiente — Frontend

| Variável | Default | Descrição |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8001` | URL do backend; em Docker usa `/api` (servido pelo nginx) |

## Deployment

### Render.com + Neon (free tier — $0/mês)

A configuração actual usa o free tier do Render para os 2 web services e o Neon (Postgres serverless) para a DB — totalmente gratuito.

**Limitações do free tier a saber antes:**
- Web services dormem após 15 min sem tráfego — primeiro request demora ~30s
- 750h/mês por serviço (chega para uso pessoal)
- Quando o backend dorme, o scheduler também dorme — os jobs de alertas não correm enquanto não houver tráfego

**Passos:**

1. **Cria a DB no Neon** (https://neon.tech)
   - Sign up (gratuito, sem cartão)
   - "New Project" → escolhe região próxima (ex: Frankfurt)
   - No dashboard, copia a "Connection string" — modo **Pooled** (importante para serverless)
   - Vai parecer-se com: `postgresql://user:pwd@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`

2. **Faz push do repo para o GitHub**

3. **Render → New → Blueprint**
   - Conecta o repo
   - O Render lê o `render.yaml` e cria 2 serviços (API + frontend)
   - **Vai pedir-te o valor de `DATABASE_URL`** (porque está marcado como `sync: false`) — cola a connection string do Neon

4. **Após o primeiro deploy:**
   - Confirma que `ALLOWED_ORIGINS` no serviço da API tem o URL final do frontend (default: `https://apex-crypto-terminal.onrender.com`)
   - Se o teu frontend ficar com outro URL, actualiza esta env var

5. **Abre o frontend** → cria conta → entras no scanner

### Render.com (plano pago — sem cold starts)

Se quiseres performance consistente, no `render.yaml` muda `plan: free` para `plan: starter` em ambos os serviços (~$14/mês total) e adiciona uma DB Render `basic-256mb` (~$1/mês). Trocar `DATABASE_URL` para `fromDatabase` em vez de `sync: false`.

### Railway (backend e frontend separados)

Cada subdirectório tem o seu `railway.json`. Cria um serviço por cada:
- `backend/` → vai ler `backend/railway.json` e fazer build do Dockerfile
- `frontend/` → idem

Para o frontend, define `BACKEND_UPSTREAM` apontando para o URL público do serviço backend.

### Vercel (apenas frontend)

```bash
cd frontend
vercel
```

O `vercel.json` trata do SPA fallback. Em **Settings → Environment Variables** define:
- `VITE_API_BASE_URL` = URL do teu backend (ex: `https://apex-crypto-api.onrender.com`)

O backend tem de estar deployado noutro serviço (Render, Railway, Fly.io, etc.).

## Pontos importantes para produção

1. **Define `DEBUG=false`** — caso contrário, qualquer request sem token entra como o primeiro user da DB. Isto é prático em dev, perigoso em produção.
2. **Gera `SECRET_KEY` único** — `openssl rand -hex 32`. Não deixes o default.
3. **Usa Postgres** — SQLite não é adequado para deployment com múltiplos workers.
4. **Configura `ALLOWED_ORIGINS`** — lista exacta dos domínios do frontend em produção, sem `*`.
5. **Considera CoinGecko Pro** se tiveres tráfego — a API pública tem rate limits agressivos.

## Endpoints principais

| Método | Path | Descrição |
|---|---|---|
| `POST` | `/auth/register` | Criar conta + devolve JWT |
| `POST` | `/auth/login` | Login → JWT |
| `GET` | `/crypto/scanner` | Top 80 moedas com score |
| `GET` | `/crypto/detail/{id}` | Detalhe completo + TVL + tokenomics |
| `GET` | `/crypto/chart/{id}` | Série temporal de preço |
| `GET` | `/market/fear-greed` | Index do dia |
| `GET/POST/PUT/DELETE` | `/watchlist` | Gestão de watchlist |
| `GET/POST/DELETE` | `/portfolios` | Portfolios |
| `POST` | `/portfolios/{id}/refresh` | Refresh manual de preços |
| `GET/POST/DELETE` | `/alerts` | Alertas |
| `GET` | `/jobs/status` | Status do scheduler |
| `POST` | `/jobs/run/check-alerts` | Trigger manual do job |

Documentação completa em `/docs` (Swagger) ou `/redoc`.

## Notas

- Em modo demo (sem internet ou CoinGecko offline), o serviço devolve dados de exemplo para BTC/ETH/SOL/LINK/BNB/XRP — útil para desenvolvimento e testes.
- A deduplicação de alertas evita spam: o mesmo (user, coin, tipo) não dispara mais que uma vez em 6 horas.
- O cache TTL é partilhado entre rotas e jobs — múltiplos consumidores beneficiam da mesma chamada à CoinGecko.

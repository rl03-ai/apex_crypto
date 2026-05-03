import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — regista todos os modelos no Base

from app.api.routes import auth, alerts, crypto, debug, health, market, portfolio, watchlist
from app.api.routes import jobs as jobs_router
from app.api.routes import signals as signals_router
from app.api.routes import whales as whales_router
from app.api.routes import decision_matrix as matrix_router
from app.api.routes import risk_strategy as risk_strategy_router
from app.api.routes import swing as swing_router
from app.api.routes import fund_mode as fund_mode_router
from app.core.config import get_settings
from app.core.database import Base, engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    description='Apex Crypto API — scanner, watchlist, portfolio, alertas e jobs.',
    version='2.0.0',
)

# ── CORS: origins from environment + local dev fallbacks ────────────────────
local_origins = [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
]
allowed_origins = list(dict.fromkeys(settings.allowed_origins_list() + local_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,     tags=['health'])
app.include_router(auth.router,       prefix='/auth',        tags=['auth'])
app.include_router(crypto.router,     prefix='/crypto',      tags=['crypto'])
app.include_router(market.router,     prefix='/market',      tags=['market'])
app.include_router(watchlist.router,  prefix='/watchlist',   tags=['watchlist'])
app.include_router(portfolio.router,  prefix='/portfolios',  tags=['portfolio'])
app.include_router(alerts.router,     prefix='/alerts',      tags=['alerts'])
app.include_router(jobs_router.router, prefix='/jobs',       tags=['jobs'])
app.include_router(signals_router.router, prefix='/signals', tags=['signals'])
app.include_router(whales_router.router,  tags=['whales'])
app.include_router(matrix_router.router,  tags=['matrix'])
app.include_router(swing_router.router,   tags=['swing'])
app.include_router(fund_mode_router.router, tags=['fund-mode'])
app.include_router(risk_strategy_router.risk_router,     tags=['risk'])
app.include_router(risk_strategy_router.strategy_router, tags=['strategy'])
app.include_router(debug.router,      prefix='/debug',       tags=['debug'])


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event('startup')
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info('DB tables verificadas/criadas.')

    from app.jobs.scheduler import start_scheduler
    start_scheduler()


@app.on_event('shutdown')
def on_shutdown() -> None:
    from app.jobs.scheduler import stop_scheduler
    stop_scheduler()


# ── Raiz ──────────────────────────────────────────────────────────────────────
@app.get('/', include_in_schema=False)
def root() -> dict:
    return {'name': settings.app_name, 'version': '2.0.0', 'docs': '/docs'}

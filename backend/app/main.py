import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — regista todos os modelos no Base

from app.api.routes import auth, alerts, crypto, debug, health, market, portfolio, watchlist
from app.api.routes import jobs as jobs_router
from app.api.routes import signals as signals_router
from app.api.routes import whales as whales_router
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

# ── CORS: Auto-detect allowed origins ──────────────────────────────────────
# Prioridade:
#   1. ALLOWED_ORIGINS env var (se definida)
#   2. Auto-detect baseado no hostname (ex: api.onrender.com → terminal.onrender.com)
#   3. Fallback local para dev
def _get_cors_origins() -> list[str]:
    """Compute allowed origins com auto-detect."""
    origins: set[str] = set()
    
    # Se ALLOWED_ORIGINS está definida, usa-a
    if settings.allowed_origins and settings.allowed_origins.strip():
        origins.update(settings.allowed_origins_list())
    
    # Auto-detect: se estamos em Render, permitir o frontend correspondente
    # Ex: apex-crypto-api.onrender.com → apex-crypto-terminal.onrender.com
    import os
    render_service = os.getenv('RENDER_SERVICE_NAME', '')
    if 'onrender.com' in render_service or 'onrender.com' in os.getenv('RENDER_EXTERNAL_URL', ''):
        # Assumir que o frontend é o mesmo hostname com -api substituído por -terminal
        frontend_url = render_service.replace('-api', '-terminal') if '-api' in render_service else 'apex-crypto-terminal'
        origins.add(f'https://{frontend_url}.onrender.com')
    
    # Fallback dev local
    origins.update(['http://localhost:5173', 'http://localhost:5174', 'http://localhost:3000'])
    
    return list(origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
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

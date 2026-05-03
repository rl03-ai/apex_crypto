import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

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


# ── Global Exception Handler with CORS ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all exceptions and always return CORS headers."""
    logger.error(f'Exception: {exc}', exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={'detail': 'Internal server error'},
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        }
    )


# ── CORS Middleware (applied early) ─────────────────────────────────────────
class CORSEarlyMiddleware(BaseHTTPMiddleware):
    """CORS on every request, especially preflight."""
    
    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        # Always respond to OPTIONS
        if request.method == 'OPTIONS':
            return Response(
                status_code=200,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS, HEAD',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept',
                    'Access-Control-Max-Age': '86400',
                }
            )
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f'Middleware error: {e}')
            response = Response(status_code=500, content='Internal error')
        
        # Force CORS on all responses
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, HEAD'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range'
        
        return response


# Add CORS middleware FIRST
app.add_middleware(CORSEarlyMiddleware)

# Then standard CORS (redundant but safe)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,  # Important: can't use with allow_origins=['*']
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

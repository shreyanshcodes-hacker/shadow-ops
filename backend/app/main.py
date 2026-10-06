from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import init_db, close_db
from app.api import api_router
from app.security.middleware import setup_middleware
from app.ai.providers import ai_provider_registry

import logging
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    format="%(message)s",
    level=getattr(logging, settings.LOG_LEVEL.upper()),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")

    # Register AI providers (placeholder for now)
    # ai_provider_registry.register(GeminiProvider())
    # ai_provider_registry.register(GrokProvider())

    yield

    # Shutdown
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title="ShadowOps API",
    description="AI-native security platform for startups and engineering teams",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.getLogger(__name__).exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}},
    )


@app.get("/")
async def root():
    return {
        "name": "ShadowOps API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
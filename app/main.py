import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup", env=settings.APP_ENV)
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title="Funding Aggregator API",
    description=(
        "Microservice for aggregating grants, scholarships, and funding opportunities "
        "from Grants.gov, NIH RePORTER, and other sources.\n\n"
        "**Authentication**: Use `/api/v1/auth/register` to create an account, "
        "then `/api/v1/auth/login` to get a Bearer token."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Routers
app.include_router(api_router, prefix="/api/v1")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Funding Aggregator",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

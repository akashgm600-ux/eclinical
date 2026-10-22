"""FastAPI Application Main Entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    # Ensure database tables exist upon API startup
    init_db()
    yield


app = FastAPI(
    title="Clinical Trial Data Quality & ETL Platform API",
    description=(
        "REST API serving clinical trial ingestion metrics, data quality audit trails, "
        "quarantine inspection, and pipeline run triggers."
    ),
    version=settings.PIPELINE_VERSION,
    lifespan=lifespan,
)

# Enable CORS for local dashboards and external consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route controllers
app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )

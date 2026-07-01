
from fastapi import FastAPI
import app.db

from app.core.settings import settings

from app.routers.dashboard import router as dashboard_router
from app.routers.auth import router as auth_router
from app.routers.ingestion import router as ingestion_router
from app.routers.customer import router as customer_router
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Customer Retention Intelligence Platform",
    version=settings.APP_VERSION,
)

# Routers
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(customer_router)


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "message": "Backend is running successfully"
    }
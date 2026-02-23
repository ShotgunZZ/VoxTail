"""Route modules for speaker recognition API."""
from fastapi import APIRouter

from routes.enrollment import router as enrollment_router
from routes.identification import router as identification_router
from routes.speakers import router as speakers_router
from routes.confirmation import router as confirmation_router
from routes.summary import router as summary_router

# Create main API router that includes all sub-routers
api_router = APIRouter(prefix="/api")
api_router.include_router(enrollment_router)
api_router.include_router(identification_router)
api_router.include_router(speakers_router)
api_router.include_router(confirmation_router)
api_router.include_router(summary_router)

__all__ = ["api_router"]

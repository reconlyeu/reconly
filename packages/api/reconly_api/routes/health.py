"""Health check endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from reconly_api.config import settings
from reconly_api.dependencies import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health/db")
async def database_health(db: Session = Depends(get_db)):
    """Database health check with actual connectivity test."""
    try:
        # Try to execute a simple query
        result = db.execute(text("SELECT 1")).scalar()

        if result == 1:
            return {
                "status": "healthy",
                "database": "connected",
                "database_url": settings.database_url.split("://")[0] + "://***",  # Hide credentials
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=503, detail="Database query returned unexpected result")

    except OperationalError as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

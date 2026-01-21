from fastapi import APIRouter, HTTPException
from app.core.config import settings
from datetime import datetime
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENV,
        "service": settings.APP_NAME,
        "checks": {}
    }
    
    all_healthy = True
    
    # Check Jira connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.JIRA_BASE_URL}/rest/api/3/serverInfo",
                auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
            )
            if response.status_code == 200:
                health_status["checks"]["jira"] = {"status": "healthy", "message": "Connected"}
            else:
                health_status["checks"]["jira"] = {"status": "degraded", "message": f"HTTP {response.status_code}"}
                all_healthy = False
    except Exception as e:
        logger.warning(f"Jira health check failed: {e}")
        health_status["checks"]["jira"] = {"status": "unhealthy", "message": str(e)}
        all_healthy = False
    
    # Check Xray connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.XRAY_BASE_URL}/api/v2/authenticate",
                json={
                    "client_id": settings.XRAY_CLIENT_ID,
                    "client_secret": settings.XRAY_CLIENT_SECRET
                }
            )
            if response.status_code == 200:
                health_status["checks"]["xray"] = {"status": "healthy", "message": "Connected"}
            else:
                health_status["checks"]["xray"] = {"status": "degraded", "message": f"HTTP {response.status_code}"}
                all_healthy = False
    except Exception as e:
        logger.warning(f"Xray health check failed: {e}")
        health_status["checks"]["xray"] = {"status": "unhealthy", "message": str(e)}
        all_healthy = False
    
    # Update overall status
    if not all_healthy:
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe for Kubernetes/container orchestration."""
    try:
        # Quick validation that critical config exists
        if not settings.JIRA_BASE_URL or not settings.XRAY_BASE_URL:
            raise HTTPException(status_code=503, detail="Service not ready: missing configuration")
        
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service not ready: {e}")


@router.get("/health/live")
async def liveness_check():
    """Liveness probe for Kubernetes/container orchestration."""
    return {"status": "alive"}
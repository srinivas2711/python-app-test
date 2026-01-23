from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from contextlib import asynccontextmanager
from app.fabric_mcp import jira_mcp_server, xray_mcp_server
from app.core.config import settings
from app.api import health_router
import logging

# Configure logging early
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize MCP server
fabric_mcp_server = FastMCP(
    name="Fabric MCP Server",
    mask_error_details=not settings.DEBUG,
)

@asynccontextmanager
async def include_mcp_servers(_: FastAPI):
    await fabric_mcp_server.import_server(jira_mcp_server, prefix="pss_fabric")
    await fabric_mcp_server.import_server(xray_mcp_server, prefix="pss_fabric")
    yield

fabric_mcp_app = fabric_mcp_server.http_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with include_mcp_servers(app):
        async with fabric_mcp_app.lifespan(app):
            yield

app = FastAPI(
    title="MCP Fabric Server",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount MCP
app.mount("/fabric", fabric_mcp_app)

# Health
@app.get("/healthy")
async def healthy():
    return {"status": "healthy"}

# CORS
origins = settings.CORS_ORIGINS.split(",")
logger.info(f"CORS configured with origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error", exc_info=True)

    if settings.ENV == "production":
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )

# API routes
app.include_router(health_router, prefix="/api")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from dotenv import load_dotenv
from app.fabric_mcp import jira_mcp_server, xray_mcp_server
from app.core.config import settings
from contextlib import asynccontextmanager
from app.api import health_router

import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the main Fabric MCP server
fabric_mcp_server = FastMCP(name="Fabric MCP Server", mask_error_details=not settings.DEBUG)

# Include other MCP servers
# A lifespan manager to include MCP servers
@asynccontextmanager
async def include_mcp_servers(_: FastAPI):
	await fabric_mcp_server.import_server(jira_mcp_server, prefix="pss_fabric")
	await fabric_mcp_server.import_server(xray_mcp_server, prefix="pss_fabric")
	yield

# Create MCP HTTP app
fabric_mcp_app = fabric_mcp_server.http_app()

# combining app lifespan with FastMCP lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
	async with include_mcp_servers(app):
		async with fabric_mcp_app.lifespan(app):
			yield

# Create FastAPI app
app = FastAPI(title="MCP Fabric Server", version="1.0.0", lifespan=lifespan)

# Mount MCP server 
app.mount("/fabric", fabric_mcp_app)
app.mount("/healthy", JSONResponse(content={"status": "healthy"}))

# CORS configuration
origins = settings.CORS_ORIGINS.split(",")
logger.info(f"CORS configured with origins: {origins}")

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Error handler example
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
	logger.error(f"Unhandled error: {exc}", exc_info=True)
	
	# Don't expose internal errors in production
	if settings.ENV == "production":
		return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
	else:
		return JSONResponse(
			status_code=500, 
			content={"detail": "Internal Server Error", "error": str(exc)}
		)

# Mount fastapi routes
app.include_router(health_router, prefix="/api")

if __name__ == "__main__":
	import uvicorn
	logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
	uvicorn.run(
		"app.main:app", 
		host=settings.HOST, 
		port=settings.PORT,
		reload=settings.DEBUG
	)

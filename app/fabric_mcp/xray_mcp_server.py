from app.services.xray_client import XrayClient
from app.core.config import settings
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import logging

logger = logging.getLogger(__name__)

xray_client = XrayClient(
    base_url=settings.XRAY_BASE_URL,
    client_id=settings.XRAY_CLIENT_ID,
    client_secret=settings.XRAY_CLIENT_SECRET
)

xray_mcp_server = FastMCP(
    name="Fabric Xray MCP Server",
    mask_error_details=not settings.DEBUG
)

@xray_mcp_server.tool(name="get_xray_test_case")
async def get_xray_test_case(test_case_key: str) -> dict:
    """Fetch an Xray test case by its key.

    Args:
        test_case_key: The Xray test case key (e.g., 'XSP-123')

    Returns:
        A dictionary containing the test case details
    """
    try:
        test_case = await xray_client.get_test_case(test_case_key)
        return test_case
    except (ValueError, PermissionError, RuntimeError) as e:
        logger.error(f"Error in get_xray_test_case tool: {e}", exc_info=True)
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_xray_test_case tool: {e}", exc_info=True)
        raise # Safe to raise. Exceptions/Error other than ToolError will be masked by FastMCP

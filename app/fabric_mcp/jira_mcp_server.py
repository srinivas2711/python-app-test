from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from app.core.config import settings
from app.services.jira_client import JiraClient
import logging

logger = logging.getLogger(__name__)

jira_client = JiraClient(
    base_url=settings.JIRA_BASE_URL,
    username=settings.JIRA_EMAIL,
    api_token=settings.JIRA_API_TOKEN,
)

jira_mcp_server = FastMCP(
    name="Fabric JIRA MCP Server",
    mask_error_details=not settings.DEBUG
)

@jira_mcp_server.tool(name="get_jira_issue")
async def get_jira_issue(issue_key: str) -> dict:
    """Fetch a Jira issue by its key with all fields including custom fields.

    Args:
        issue_key: The Jira issue key (e.g., 'PROJ-123')

    Returns:
        A dictionary containing the issue details with custom field names resolved
    """
    try:
        issue = await jira_client.get_issue(issue_key)
        return issue
    except (ValueError, PermissionError, RuntimeError) as e:
        logger.error(f"Error in get_jira_issue tool: {e}", exc_info=True)
        # Raise a ToolError to return error response
        raise ToolError(str(e))
    except Exception as e:
        # Truly unexpected errors
        logger.critical(f"Unexpected error in get_jira_issue tool: {e}", exc_info=True)
        raise # Safe to raise. Exceptions/Error other than ToolError will be masked by FastMCP

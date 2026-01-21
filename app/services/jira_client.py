import httpx
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 30.0


class JiraClient:
    """A simple Jira client to interact with Jira's REST API."""
    def __init__(self, base_url: Optional[str], username: Optional[str], api_token: Optional[str]):
        if not base_url or not username or not api_token:
            raise ValueError("Jira base_url, username, and api_token are required")
        
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._http_client

    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            logger.info("JiraClient HTTP client closed")

    async def get_issue(self, issue_key: str, include_all_fields: bool = True) -> dict:
        """Fetch a Jira issue by its key with all fields including custom fields."""
        # Validate issue key format
        if not issue_key or not self._is_valid_issue_key(issue_key):
            logger.warning(f"Invalid issue key format: {issue_key}")
            raise ValueError(f"Invalid issue key format: {issue_key}")

        auth = (self.username, self.api_token)
        client = await self._get_http_client()
        
        try:
            # Fetch the issue
            issue_url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
            
            logger.info(f"Fetching Jira issue: {issue_key}")
            response = await client.get(
                issue_url,
                auth=auth,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            # Fetch field metadata to get custom field names
            fields_url = f"{self.base_url}/rest/api/3/field"
            logger.debug("Fetching Jira field metadata")
            fields_response = await client.get(
                fields_url,
                auth=auth,
                headers={"Accept": "application/json"},
            )
            fields_response.raise_for_status()

            # Create a mapping of field IDs to names
            field_metadata = fields_response.json()
            field_name_map = {field["id"]: field["name"] for field in field_metadata}

            fields = data.get("fields", {})

            # Helper function to safely extract nested values
            def safe_get(obj, key, default=None):
                if obj and isinstance(obj, dict):
                    return obj.get(key, default)
                return default

            # Always include basic info
            issue_info = {
                "key": data.get("key"),
                "id": data.get("id"),
                "self_url": data.get("self"),
                "summary": fields.get("summary"),
                "description": fields.get("description"),
                "status": safe_get(fields.get("status"), "name"),
                "priority": safe_get(fields.get("priority"), "name"),
                "assignee": safe_get(
                    fields.get("assignee"), "displayName", "Unassigned"
                ),
                "reporter": safe_get(fields.get("reporter"), "displayName"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "issue_type": safe_get(fields.get("issuetype"), "name"),
                "project": {
                    "key": safe_get(fields.get("project"), "key"),
                    "name": safe_get(fields.get("project"), "name"),
                },
                "labels": fields.get("labels", []),
            }

            if include_all_fields:
                # Add all fields with resolved names
                all_fields = {}
                for field_id, field_value in fields.items():
                    # Get the human-readable field name
                    field_name = field_name_map.get(field_id, field_id)

                    # Skip if already in basic info (avoid duplication)
                    if field_name in [
                        "Summary",
                        "Description",
                        "Status",
                        "Priority",
                        "Assignee",
                        "Reporter",
                        "Created",
                        "Updated",
                        "Issue Type",
                        "Project",
                        "Labels",
                    ]:
                        continue

                    # Simplify complex objects
                    if field_value is None:
                        all_fields[field_name] = None
                    elif isinstance(field_value, dict):
                        # Extract useful info from complex objects
                        if "name" in field_value:
                            all_fields[field_name] = field_value.get("name")
                        elif "displayName" in field_value:
                            all_fields[field_name] = field_value.get("displayName")
                        elif "value" in field_value:
                            all_fields[field_name] = field_value.get("value")
                        else:
                            all_fields[field_name] = field_value
                    elif isinstance(field_value, list):
                        # Handle arrays
                        if len(field_value) > 0 and isinstance(field_value[0], dict):
                            # Extract names from list of objects
                            all_fields[field_name] = [
                                item.get("name")
                                or item.get("displayName")
                                or item.get("value")
                                or item
                                for item in field_value
                            ]
                        else:
                            all_fields[field_name] = field_value
                    else:
                        all_fields[field_name] = field_value

                issue_info["all_fields"] = all_fields

            logger.info(f"Successfully fetched Jira issue: {issue_key}")
            return issue_info

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error fetching Jira issue {issue_key}: {status_code}")
            
            if status_code == 404:
                raise ValueError(f"Issue {issue_key} does not exist")
            elif status_code == 401:
                raise PermissionError("Authentication failed. Check Jira credentials.")
            elif status_code == 403:
                raise PermissionError(f"Access forbidden to issue {issue_key}")
            else:
                raise RuntimeError(f"Failed to fetch issue {issue_key}: HTTP {status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Network error fetching Jira issue {issue_key}: {e}")
            raise RuntimeError(f"Network error fetching issue: {e}")
            
        except ValueError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error fetching Jira issue {issue_key}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error fetching issue: {e}")

    @staticmethod
    def _is_valid_issue_key(issue_key: str) -> bool:
        """Validate Jira issue key format (e.g., PROJ-123)."""
        if not issue_key:
            return False
        # Pattern: 1+ uppercase letters, hyphen, 1+ digits
        pattern = r'^[A-Z][A-Z0-9]*-[0-9]+$'
        return bool(re.match(pattern, issue_key))

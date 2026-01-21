import httpx
import time
import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Constants
TOKEN_REFRESH_BUFFER_SECONDS = 60
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class XrayClient:
    """A simple Xray client to interact with Xray's API."""
    def __init__(self, base_url: Optional[str], client_id: Optional[str], client_secret: Optional[str], expires_in: int = 86400):
        if not base_url or not client_id or not client_secret:
            raise ValueError("Xray base_url, client_id, and client_secret are required")
        
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"{self.base_url}/api/v2/authenticate"
        self.expires_in = expires_in

        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._token_lock = asyncio.Lock()
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
            logger.info("XrayClient HTTP client closed")

    async def _fetch_token(self):
        """Fetch new access token using client_credentials flow"""
        client = await self._get_http_client()
        
        try:
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            logger.info("Fetching new Xray authentication token")
            response = await client.post(
                self.token_url,
                json=payload,
            )
            response.raise_for_status()
            
            # Parse token from response
            access_token = response.text.strip()
            
            # Remove surrounding quotes if present
            if access_token.startswith('"') and access_token.endswith('"'):
                access_token = access_token[1:-1]
            
            self._token = access_token

            # Set token expiry time
            self._token_expires_at = time.time() + self.expires_in - TOKEN_REFRESH_BUFFER_SECONDS
            logger.info("Xray authentication token refreshed successfully")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to authenticate with Xray API: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Xray authentication: {e}")
            raise

    async def _ensure_valid_token(self):
        """Refresh token if missing or about to expire (thread-safe)"""
        # Fast path: check without lock
        if self._token and time.time() < self._token_expires_at:
            return
        
        # Slow path: acquire lock and refresh
        async with self._token_lock:
            # Double-check after acquiring lock (another coroutine might have refreshed)
            if not self._token or time.time() >= self._token_expires_at:
                await self._fetch_token() 

    async def get_test_case(self, test_case_key: str) -> dict:
        """Fetch an Xray test case by its key."""
        # Validate test case key format
        if not test_case_key or not self._is_valid_issue_key(test_case_key):
            logger.warning(f"Invalid test case key format: {test_case_key}")
            raise ValueError(f"Invalid test case key format: {test_case_key}")
        
        await self._ensure_valid_token()
        client = await self._get_http_client()
        
        try:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            }
            
            # Use parameterized query to prevent injection
            payload = {
                "query": """query GetTest($jql: String!, $limit: Int!) { 
                        getTests(jql: $jql, limit: $limit) {
                            total
                            results {
                                issueId
                                projectId
                                jira(fields: ["key", "summary", "description", "priority", "status", "labels"])
                                testType {
                                    name
                                    kind
                                }
                                steps {
                                    id
                                    action
                                    data
                                    result
                                }
                                gherkin
                                unstructured
                            }
                        }
                    }""",
                "variables": {
                    "jql": f"key = {test_case_key}",  # GraphQL escapes this properly
                    "limit": 100
                }
            }

            test_case_url = f"{self.base_url}/api/v2/graphql"
            
            logger.info(f"Fetching Xray test case: {test_case_key}")
            response = await client.post(
                test_case_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            data = data.get("data", {}).get("getTests", {})

            if data.get("total", 0) == 0:
                logger.warning(f"Test case not found: {test_case_key}")
                raise ValueError(f"Test case {test_case_key} not found")

            results = data.get("results", [])
            if not results:
                logger.warning(f"Test case not found: {test_case_key}")
                raise ValueError(f"Test case {test_case_key} not found")

            logger.info(f"Successfully fetched test case: {test_case_key}")
            return results[0]

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error fetching test case {test_case_key}: {status_code}")
            
            if status_code == 404:
                raise ValueError(f"Test case {test_case_key} does not exist")
            elif status_code == 401:
                raise PermissionError("Authentication failed. Check Xray credentials.")
            elif status_code == 403:
                raise PermissionError(f"Access forbidden to test case {test_case_key}")
            else:
                raise RuntimeError(f"Failed to fetch test case {test_case_key}: HTTP {status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Network error fetching test case {test_case_key}: {e}")
            raise RuntimeError(f"Network error fetching test case: {e}")
            
        except ValueError:
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error fetching test case {test_case_key}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error fetching test case: {e}")

    @staticmethod
    def _is_valid_issue_key(issue_key: str) -> bool:
        """Validate Jira/Xray issue key format (e.g., PROJ-123)."""
        if not issue_key:
            return False
        # Pattern: 1+ uppercase letters, hyphen, 1+ digits
        pattern = r'^[A-Z][A-Z0-9]*-[0-9]+$'
        return bool(re.match(pattern, issue_key))

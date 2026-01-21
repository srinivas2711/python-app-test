from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationError
import os
import sys
import logging

# Load .env file once when config module is imported
load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # JIRA configuration (required)
    JIRA_EMAIL: str
    JIRA_API_TOKEN: str
    JIRA_BASE_URL: str

    # Xray configuration (required)
    XRAY_CLIENT_ID: str
    XRAY_CLIENT_SECRET: str
    XRAY_BASE_URL: str

    # CORS configuration
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    # Server configuration
    APP_NAME: str = "Fabric Agent Server"
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    @field_validator("JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_BASE_URL")
    @classmethod
    def validate_jira_config(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} is required but not set")
        return v.strip()

    @field_validator("XRAY_CLIENT_ID", "XRAY_CLIENT_SECRET", "XRAY_BASE_URL")
    @classmethod
    def validate_xray_config(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} is required but not set")
        return v.strip()

    @field_validator("JIRA_BASE_URL", "XRAY_BASE_URL")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Base URL must start with http:// or https://")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        v = v.strip()
        if v == "*":
            logger.warning(
                "CORS_ORIGINS is set to '*' (allow all origins). "
                "This is insecure and should not be used in production!"
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


def load_settings() -> Settings:
    """Load and validate settings, exit with error if validation fails."""
    try:
        return Settings()
    except ValidationError as e:
        logger.error("Configuration validation failed:")
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            logger.error(f"  - {field}: {error['msg']}")
        logger.error(
            "\nPlease check your .env file and ensure all required environment variables are set."
        )
        sys.exit(1)


# Create settings instance and validate on import
try:
    settings = load_settings()
    logger.info(f"Configuration loaded successfully (ENV={settings.ENV})")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    sys.exit(1)
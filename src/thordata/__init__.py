"""Thordata Python SDK for SERP and Web Scraper requests."""

from ._version import __version__
from .client import (
    DEFAULT_API_URL,
    INTEGRATION_PLATFORM,
    INTEGRATION_SOURCE,
    SUPPORTED_ENGINES,
    SearchResponse,
    ThorDataClient,
)
from .errors import (
    ThorDataAPIError,
    ThorDataAuthenticationError,
    ThorDataConfigurationError,
    ThorDataConnectionError,
    ThorDataError,
    ThorDataInvalidRequestError,
    ThorDataNotCollectedError,
    ThorDataPermissionError,
    ThorDataRateLimitError,
    ThorDataTimeoutError,
)
from .web_scraper import (
    DEFAULT_MAX_WAIT_SECONDS,
    SUPPORTED_WEB_SCRAPERS,
    ThorDataWebScraperError,
    WebScraperResponse,
)

Client = ThorDataClient

__all__ = [
    "Client",
    "DEFAULT_API_URL",
    "DEFAULT_MAX_WAIT_SECONDS",
    "INTEGRATION_PLATFORM",
    "INTEGRATION_SOURCE",
    "SUPPORTED_ENGINES",
    "SUPPORTED_WEB_SCRAPERS",
    "SearchResponse",
    "ThorDataAPIError",
    "ThorDataAuthenticationError",
    "ThorDataClient",
    "ThorDataConfigurationError",
    "ThorDataConnectionError",
    "ThorDataError",
    "ThorDataInvalidRequestError",
    "ThorDataNotCollectedError",
    "ThorDataPermissionError",
    "ThorDataRateLimitError",
    "ThorDataTimeoutError",
    "ThorDataWebScraperError",
    "WebScraperResponse",
    "__version__",
]

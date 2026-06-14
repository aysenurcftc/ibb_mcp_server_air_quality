import logging
from abc import ABC, abstractmethod
from typing import Any
import httpx

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """
    Base class for all API adapters.
    Each adapter:
        Connects to its respective API.
        Converts raw incoming data into standard models.
        Implements error handling.
    """

    SOURCE_NAME: str = "unknown"

    def __init__(
        self, base_url: str, api_key: str | None = None, timeout: float = 30.0
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )
        logger.info(f"{self.SOURCE_NAME} adapter initialized: {self.base_url}")

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def get(self, endpoint: str, params: dict | None = None) -> Any:
        """Send a GET request."""
        if not self._http_client:
            raise RuntimeError("Adapter is not connected. connect() must be called.")
        response = await self._http_client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()

    @abstractmethod
    async def health_check(self) -> bool:
        """API health check."""
        ...

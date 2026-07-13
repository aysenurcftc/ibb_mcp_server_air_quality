import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """User-facing error propagated from the adapter to the MCP tool layer."""


# Retryable exceptions: connection issues and 5xx / 429 status codes.
# 4xx (400, 404, etc.) are client errors and won't be resolved by retrying -> do not retry.
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)


def _is_retryable_status(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 502, 503, 504)
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


class BaseAdapter(ABC):
    """
    Base class for all API adapters.
    Each adapter:
        - Connects to its respective API.
        - Translates raw data into standard models.
        - Handles retry and error management here.
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
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError,) + RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _get_with_retry(self, endpoint: str, params: dict | None) -> httpx.Response:
        response = await self._http_client.get(endpoint, params=params)
        response.raise_for_status()
        return response

    async def get(self, endpoint: str, params: dict | None = None) -> Any:
        """
        Sends a GET request. Automatically retries 3 times with exponential backoff 
        for connection errors and 429/502/503/504 status codes. Does not retry 
        on 4xx statuses (e.g., 400, 404) and raises AdapterError immediately.
        """
        if not self._http_client:
            raise RuntimeError("Adapter is not connected. connect() must be called.")

        try:
            response = await self._get_with_retry(endpoint, params)
            return response.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error(f"[{self.SOURCE_NAME}] HTTP {status} on {endpoint}: {e}")
            if status in (429, 502, 503, 504):
                raise AdapterError(
                    f"{self.SOURCE_NAME} API is currently not responding (HTTP {status}). "
                    "Please try again shortly."
                ) from e
            raise AdapterError(f"{self.SOURCE_NAME} API rejected the request (HTTP {status}).") from e
        except RETRYABLE_EXCEPTIONS as e:
            logger.error(f"[{self.SOURCE_NAME}] Connection error on {endpoint}: {e}")
            raise AdapterError(
                f"Could not reach {self.SOURCE_NAME} API (connection timeout)."
            ) from e

    @abstractmethod
    async def health_check(self) -> bool:
        """API health check."""
        ...
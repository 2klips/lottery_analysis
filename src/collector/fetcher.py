"""HTTP fetcher for Pension Lottery 720+ APIs."""

from __future__ import annotations

import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from ..utils.logging_config import get_logger

REQUEST_DELAY = 2.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15
BACKOFF_FACTOR = 2.0

BASE_URL = "https://dhlottery.co.kr"
ROUND_LIST_URL = f"{BASE_URL}/pt720/selectPstPt720WnList.do"
ROUND_INFO_URL = f"{BASE_URL}/pt720/selectPstPt720Info.do"
ROUND_WIN_INFO_URL = f"{BASE_URL}/pt720/selectPstPt720WnInfo.do"
MAIN_URL = f"{BASE_URL}/common.do?method=main"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://dhlottery.co.kr/pt720/result",
    "X-Requested-With": "XMLHttpRequest",
}

logger = get_logger(__name__)


class RateLimitError(Exception):
    """Raised when server-side rate limiting is detected."""


class FetchError(Exception):
    """Raised when a fetch operation fails after retries."""


class PensionFetcher:
    """HTTP client for Pension Lottery 720+ APIs with retry logic."""

    def __init__(self, delay: float = REQUEST_DELAY) -> None:
        """Initialize fetcher session and throttling state.

        Args:
            delay: Minimum seconds between consecutive requests.
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_request_time = 0.0
        self.consecutive_errors = 0

    def _wait_for_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send HTTP request with exponential backoff and circuit breaker.

        Args:
            method: HTTP method, such as ``GET``.
            url: Target endpoint.
            **kwargs: Additional ``requests`` arguments.

        Returns:
            Successful HTTP response.

        Raises:
            FetchError: If all retries are exhausted.
        """
        last_exception: Exception | None = None
        method_upper = method.upper()

        for attempt in range(MAX_RETRIES):
            try:
                if self.consecutive_errors >= 5:
                    logger.warning("Circuit breaker activated. Waiting 30 seconds.")
                    time.sleep(30)
                    self.consecutive_errors = 0

                self._wait_for_rate_limit()
                response = self.session.request(
                    method=method_upper,
                    url=url,
                    timeout=REQUEST_TIMEOUT,
                    **kwargs,
                )

                if response.status_code in {429, 503}:
                    raise RateLimitError(f"Rate limit status code: {response.status_code}")

                response.raise_for_status()
                self.consecutive_errors = 0
                return response
            except (requests.RequestException, RateLimitError) as error:
                self.consecutive_errors += 1
                last_exception = error

                if attempt < MAX_RETRIES - 1:
                    backoff_seconds = BACKOFF_FACTOR ** attempt
                    logger.warning(
                        "Request failed (%s %s), retry %s/%s in %.1f sec: %s",
                        method_upper,
                        url,
                        attempt + 1,
                        MAX_RETRIES,
                        backoff_seconds,
                        error,
                    )
                    time.sleep(backoff_seconds)

        raise FetchError(f"Failed to fetch {url} after {MAX_RETRIES} retries") from last_exception

    def fetch_all_rounds(self) -> str:
        """Fetch all rounds data from the list API.

        Returns:
            Raw JSON response text containing all rounds.
        """
        response = self._request_with_retry("GET", ROUND_LIST_URL)
        return response.text

    def fetch_round_detail(self, round_number: int) -> str:
        """Fetch detailed info for a specific round.

        Args:
            round_number: Target round number.

        Returns:
            Raw JSON response text.
        """
        response = self._request_with_retry(
            "GET",
            ROUND_INFO_URL,
            params={"srchPsltEpsd": round_number},
        )
        return response.text

    def fetch_round_winners(self, round_number: int) -> str:
        """Fetch winner count info for a specific round.

        Args:
            round_number: Target round number.

        Returns:
            Raw JSON response text.
        """
        response = self._request_with_retry(
            "GET",
            ROUND_WIN_INFO_URL,
            params={"srchPsltEpsd": round_number},
        )
        return response.text

    def fetch_latest_round_number(self) -> int:
        """Fetch the latest round number from the main page.

        Returns:
            Latest round number.

        Raises:
            FetchError: If HTML parsing fails.
        """
        response = self._request_with_retry("GET", MAIN_URL, headers={"Accept": "text/html"})
        soup = BeautifulSoup(response.text, "lxml")
        tag = soup.select_one("strong#drwNo720")

        if tag is None or not tag.text.strip().isdigit():
            raise FetchError("Failed to parse latest round number from main page HTML")

        return int(tag.text.strip())

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

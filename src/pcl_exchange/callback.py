from __future__ import annotations

import logging
from typing import Optional

import requests
from pydantic import BaseModel
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from .builder import build_response_message
from .models import PCLEnvelope, PCLError, PCLErrorCode

logger = logging.getLogger(__name__)

# HTTP statuses worth retrying; anything else is treated as a permanent failure.
TRANSIENT_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class _TransientCallbackError(Exception):
    """Raised for connection/timeout errors or a transient HTTP status, to trigger a retry."""


class CallbackResult(BaseModel):
    """Outcome of a single `CallbackClient.send()` call."""
    success: bool
    status_code: Optional[int] = None
    attempts: int
    error: Optional[PCLError] = None


class CallbackClient:
    """Delivers signed ack/nack response messages to an envelope's `respondTo` URI."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: float = 10.0,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base

    def _post_once(self, respond_to: str, body: str) -> requests.Response:
        headers = {"Content-Type": "application/ld+json"}
        try:
            response = self._session.post(respond_to, data=body, headers=headers, timeout=self._timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise _TransientCallbackError(str(e)) from e

        if response.status_code in TRANSIENT_HTTP_STATUS_CODES:
            raise _TransientCallbackError(f"Transient HTTP status {response.status_code}")

        return response

    def send(
        self,
        respond_to: str,
        envelope: PCLEnvelope,
        content: Optional[PCLError] = None,
    ) -> CallbackResult:
        """POSTs `envelope` (+ optional `content`) to `respond_to`, retrying transient failures."""
        body = build_response_message(envelope, content).to_json()
        attempts = 0

        def _attempt() -> requests.Response:
            nonlocal attempts
            attempts += 1
            return self._post_once(respond_to, body)

        retryer: Retrying = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=self._backoff_base),
            retry=retry_if_exception_type(_TransientCallbackError),
            reraise=True,
        )

        try:
            response = retryer(_attempt)
        except _TransientCallbackError as e:
            logger.warning("Callback delivery to %s failed after %d attempt(s): %s", respond_to, attempts, e)
            return CallbackResult(
                success=False,
                attempts=attempts,
                error=PCLError(code=PCLErrorCode.TEMPORARY_FAILURE, reason=str(e), retriable=True),
            )
        except requests.exceptions.RequestException as e:
            logger.error("Callback delivery to %s raised an unexpected error: %s", respond_to, e)
            return CallbackResult(
                success=False,
                attempts=attempts,
                error=PCLError(code=PCLErrorCode.INTERNAL_ERROR, reason=str(e), retriable=False),
            )

        if not response.ok:
            return CallbackResult(
                success=False,
                status_code=response.status_code,
                attempts=attempts,
                error=PCLError(
                    code=PCLErrorCode.INTERNAL_ERROR,
                    reason=f"Receiver responded with HTTP {response.status_code}",
                    http_status=response.status_code,
                    retriable=False,
                ),
            )

        return CallbackResult(success=True, status_code=response.status_code, attempts=attempts)

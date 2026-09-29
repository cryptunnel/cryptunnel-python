"""Exceptions raised by the client - branch on the type, read the API code from ``code``."""

from __future__ import annotations

from typing import Any


class CryptunnelError(Exception):
    """Base for every error this package raises."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        # The raw API code, e.g. PAYMENT_ALREADY_EXISTS, CURRENCY_NOT_FOUND, WALLET_NOT_FOUND
        self.code = code
        self.status = status


class AuthenticationError(CryptunnelError):
    """401: wrong merchant id, wrong or rotated key, or a suspended merchant."""


class NotFoundError(CryptunnelError):
    """404: the payment or currency does not exist for this merchant."""


class ValidationError(CryptunnelError):
    """400: the request was rejected, see ``code`` for which rule."""


class RateLimitError(CryptunnelError):
    """429: too many requests. ``retry_after`` is None when the API sends no header."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, code=code, status=status)
        self.retry_after = retry_after


class ApiError(CryptunnelError):
    """A server-side failure or a transport error."""


class PaymentTimeoutError(CryptunnelError):
    """``wait_for_payment`` gave up before the payment reached a terminal status."""


def error_from_response(status: int, payload: Any, retry_after: float | None = None) -> CryptunnelError:
    """Map an API error response onto the exception hierarchy."""
    body = payload if isinstance(payload, dict) else {}
    code = body.get("code")
    message = body.get("message") or f"Cryptunnel API returned {status}"

    if status == 401:
        return AuthenticationError(message, code=code, status=status)
    if status == 404:
        return NotFoundError(message, code=code, status=status)
    if status == 429:
        return RateLimitError(message, code=code, status=status, retry_after=retry_after)
    if status == 400:
        return ValidationError(message, code=code, status=status)
    return ApiError(message, code=code, status=status)

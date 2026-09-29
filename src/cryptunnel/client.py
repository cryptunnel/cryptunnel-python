"""The Cryptunnel API clients: ``Cryptunnel`` (async) and ``CryptunnelSync``."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Mapping

import httpx

from .errors import ApiError, PaymentTimeoutError, RateLimitError, error_from_response

DEFAULT_BASE_URL = "https://api.cryptunnel.io"
DEFAULT_TIMEOUT = 30.0

#: Statuses a payment never leaves.
TERMINAL_STATUSES = frozenset({"confirmed", "confirmed_manual", "failed", "expired"})


class _BaseClient:
    """Request building and error mapping, shared by the async and the sync client.

    The endpoint methods below are plain functions returning ``self._request(...)``: on the async
    client that is a coroutine to await, on the sync client the parsed response.
    """

    def __init__(
        self,
        merchant_id: str,
        api_key: str,
        sandbox: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        self.base_url = base_url.rstrip("/")
        self._options: dict[str, Any] = {
            "base_url": self.base_url,
            "headers": {"x-merchant-id": merchant_id, "x-api-key": api_key},
            "timeout": timeout,
        }

    def create_widget_payment(
        self,
        amount: float,
        currency: str,
        external_id: str,
        *,
        success_url: str | None = None,
        fail_url: str | None = None,
        callback_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        fee_payer: str | None = None,
    ):
        """Create a payment and get the widget url to send the payer to."""
        body = self._payment_body(amount, currency, external_id, callback_url, metadata, fee_payer)
        body.update(_present(success_url=success_url, fail_url=fail_url))
        return self._request("POST", "/v1/payments/widget", json=body)

    def create_h2h_payment(
        self,
        amount: float,
        currency: str,
        external_id: str,
        target_currency: str,
        *,
        auto_trace: bool = False,
        callback_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        fee_payer: str | None = None,
    ):
        """Create a payment and get the wallet address and crypto amount to show yourself.

        ``target_currency`` must be one of the codes ``list_currencies`` returns.
        """
        body = self._payment_body(amount, currency, external_id, callback_url, metadata, fee_payer)
        body["target_currency"] = target_currency
        body["auto_trace"] = auto_trace
        return self._request("POST", "/v1/payments/h2h", json=body)

    def get_payment(self, payment_id: str):
        """Read one payment by its Cryptunnel id."""
        return self._request("GET", f"/v1/payments/{payment_id}")

    def list_payments(self, limit: int = 20, offset: int = 0):
        """List your payments, newest first."""
        return self._request("GET", "/v1/payments", params={"limit": limit, "offset": offset})

    def list_currencies(self):
        """List the currencies you can receive - exactly the values ``target_currency`` accepts."""
        return self._request("GET", "/v1/currencies", params={"is_test": _flag(self.sandbox)})

    def get_merchant(self):
        """Read your merchant - the call that tells you the credentials work."""
        return self._request("GET", "/v1/merchants")

    def _payment_body(
        self,
        amount: float,
        currency: str,
        external_id: str,
        callback_url: str | None,
        metadata: Mapping[str, Any] | None,
        fee_payer: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "external_id": external_id,
            "is_test": self.sandbox,
        }
        body.update(_present(callback_url=callback_url, metadata=metadata, fee_payer=fee_payer))
        return body

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @staticmethod
    def _payload(response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.is_success:
            return payload
        raise error_from_response(response.status_code, payload, _retry_after(response.headers))


class Cryptunnel(_BaseClient):
    """Async client - the one to use inside a bot or a web framework.

    ```python
    async with Cryptunnel(merchant_id, api_key, sandbox=True) as cryptunnel:
        payment = await cryptunnel.create_widget_payment(10, "USD", "order-1")
    ```
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._http = httpx.AsyncClient(**self._options)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise ApiError(f"Request to {path} failed: {error}") from error
        return self._payload(response)

    async def wait_for_payment(
        self,
        payment_id: str,
        *,
        timeout: float = 1800,
        first_delay: float = 5,
        max_delay: float = 30,
    ) -> Any:
        """Poll until the payment reaches a terminal status.

        For scripts and development. In production the webhook is the guarantee: a buyer who closes
        the page still gets a callback, a polling process that dies does not.
        """
        waiter = _Waiter(timeout, first_delay, max_delay)
        delay = waiter.next_delay()
        while True:
            await asyncio.sleep(delay)
            if waiter.expired():
                raise PaymentTimeoutError(f"Payment {payment_id} did not settle within {timeout} seconds")
            try:
                payment = await self.get_payment(payment_id)
            except RateLimitError as error:
                delay = waiter.next_delay(error.retry_after)
                continue
            if payment.get("status") in TERMINAL_STATUSES:
                return payment
            delay = waiter.next_delay()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "Cryptunnel":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


class CryptunnelSync(_BaseClient):
    """Blocking mirror of :class:`Cryptunnel` for scripts and one-off calls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._http = httpx.Client(**self._options)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise ApiError(f"Request to {path} failed: {error}") from error
        return self._payload(response)

    def wait_for_payment(
        self,
        payment_id: str,
        *,
        timeout: float = 1800,
        first_delay: float = 5,
        max_delay: float = 30,
    ) -> Any:
        """Poll until the payment reaches a terminal status - see :meth:`Cryptunnel.wait_for_payment`."""
        waiter = _Waiter(timeout, first_delay, max_delay)
        delay = waiter.next_delay()
        while True:
            time.sleep(delay)
            if waiter.expired():
                raise PaymentTimeoutError(f"Payment {payment_id} did not settle within {timeout} seconds")
            try:
                payment = self.get_payment(payment_id)
            except RateLimitError as error:
                delay = waiter.next_delay(error.retry_after)
                continue
            if payment.get("status") in TERMINAL_STATUSES:
                return payment
            delay = waiter.next_delay()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CryptunnelSync":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class _Waiter:
    """Polling pace: exponential backoff, capped, never sleeping past the deadline."""

    def __init__(self, timeout: float, first_delay: float, max_delay: float) -> None:
        self.deadline = time.monotonic() + timeout
        self.delay = first_delay
        self.max_delay = max_delay

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def next_delay(self, retry_after: float | None = None) -> float:
        # The API sends Retry-After on a 429, but the backoff has to stand on its own if it ever stops
        delay = self.delay if retry_after is None else retry_after
        self.delay = min(self.delay * 2, self.max_delay)
        return max(0.0, min(delay, self.deadline - time.monotonic()))


def _retry_after(headers: Mapping[str, Any]) -> float | None:
    value = headers.get("retry-after")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _present(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}

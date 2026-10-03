from __future__ import annotations

import re

import httpx
import pytest

from cryptunnel import (
    ApiError,
    AuthenticationError,
    Cryptunnel,
    CryptunnelSync,
    NotFoundError,
    RateLimitError,
    ValidationError,
    user_agent,
)


def client_returning(status: int, payload: dict, headers: dict | None = None):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=payload, headers=headers)

    cryptunnel = CryptunnelSync("merchant-id", "ct_live_key", sandbox=True)
    cryptunnel._http = httpx.Client(transport=httpx.MockTransport(handler), **cryptunnel._options)
    return cryptunnel, seen


def test_sandbox_marks_creates_as_test_payments():
    cryptunnel, seen = client_returning(200, {"id": "pay-1", "url": "https://pay.cryptunnel.io/pay-1"})

    payment = cryptunnel.create_widget_payment(10, "USD", "order-1", success_url="https://shop/ok")

    assert payment["url"] == "https://pay.cryptunnel.io/pay-1"
    body = seen[0].read().decode()
    assert '"is_test": true' in body.replace('":', '": ')
    assert seen[0].headers["x-merchant-id"] == "merchant-id"
    assert "fail_url" not in body


def test_sandbox_asks_for_the_testnet_currency_family():
    cryptunnel, seen = client_returning(200, {})

    cryptunnel.list_currencies()

    assert seen[0].url.params["is_test"] == "true"


def test_h2h_sends_the_target_currency():
    cryptunnel, seen = client_returning(200, {"id": "pay-1"})

    cryptunnel.create_h2h_payment(10, "USD", "order-1", "USDT")

    assert '"target_currency"' in seen[0].read().decode()
    assert seen[0].url.path == "/v1/payments/h2h"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (404, NotFoundError),
        (500, ApiError),
    ],
)
def test_error_status_maps_to_its_exception(status, expected):
    cryptunnel, _ = client_returning(status, {"code": "WALLET_NOT_FOUND", "message": "Wallet not found"})

    with pytest.raises(expected) as raised:
        cryptunnel.get_merchant()

    assert raised.value.code == "WALLET_NOT_FOUND"
    assert raised.value.status == status


def test_rate_limit_carries_retry_after_when_the_header_is_there():
    cryptunnel, _ = client_returning(429, {"code": "TOO_MANY"}, {"retry-after": "12"})

    with pytest.raises(RateLimitError) as raised:
        cryptunnel.get_merchant()

    assert raised.value.retry_after == 12


def test_rate_limit_without_a_header_leaves_retry_after_unset():
    cryptunnel, _ = client_returning(429, {"code": "TOO_MANY"})

    with pytest.raises(RateLimitError) as raised:
        cryptunnel.get_merchant()

    assert raised.value.retry_after is None


def test_transport_failures_surface_as_api_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    cryptunnel = CryptunnelSync("merchant-id", "ct_live_key")
    cryptunnel._http = httpx.Client(transport=httpx.MockTransport(handler), **cryptunnel._options)

    with pytest.raises(ApiError):
        cryptunnel.get_merchant()


async def test_the_async_client_maps_errors_the_same_way():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "INVALID_CREDENTIALS", "message": "Invalid credentials"})

    cryptunnel = Cryptunnel("merchant-id", "ct_live_key")
    cryptunnel._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), **cryptunnel._options)

    with pytest.raises(AuthenticationError) as raised:
        await cryptunnel.get_payment("pay-1")

    assert raised.value.code == "INVALID_CREDENTIALS"
    await cryptunnel.close()


def test_requests_carry_the_sdk_user_agent():
    cryptunnel, seen = client_returning(200, {})

    cryptunnel.get_merchant()

    assert re.fullmatch(r"cryptunnel-python/\d+\.\d+\.\d+\S* python/\S+ httpx/\S+ \(\S+ \S+\)", seen[0].headers["user-agent"])


def test_the_app_name_is_appended_to_the_user_agent():
    cryptunnel = CryptunnelSync("merchant-id", "ct_live_key", app="my-shop/2.0")

    assert cryptunnel._options["headers"]["User-Agent"].endswith(" my-shop/2.0")
    assert user_agent("x/1").startswith("cryptunnel-python/")


def test_base_url_is_honoured():
    local = CryptunnelSync("merchant-id", "ct_live_key", base_url="http://localhost:3000/")
    assert local._options["base_url"] == "http://localhost:3000"

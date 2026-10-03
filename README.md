# cryptunnel

[![Test](https://github.com/cryptunnel/cryptunnel-python/actions/workflows/test.yml/badge.svg)](https://github.com/cryptunnel/cryptunnel-python/actions/workflows/test.yml) [![PyPI](https://img.shields.io/pypi/v/cryptunnel)](https://pypi.org/project/cryptunnel/) [![Python](https://img.shields.io/pypi/pyversions/cryptunnel)](https://pypi.org/project/cryptunnel/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python SDK for [Cryptunnel](https://cryptunnel.io) - accept crypto payments straight into your own
wallets. Async-first for bots on aiogram, with a blocking mirror for scripts.

```bash
pip install cryptunnel
```

`httpx` is the only dependency. Python 3.10+.

## Create a sandbox payment

```python
from cryptunnel import CryptunnelSync

cryptunnel = CryptunnelSync("<merchant id>", "<api key>", sandbox=True)

print(cryptunnel.get_merchant())  # your credentials work if this prints your merchant

payment = cryptunnel.create_widget_payment(
    amount=10,
    currency="USD",
    external_id="order-1",
    success_url="https://example.com/thanks",
)
print(payment["url"])  # send the buyer here
```

`sandbox=True` sets `is_test` on every payment it creates: the payer is offered testnet currencies
only, and the payment is excluded from your stats and fees. It is the same host and the same key -
the sandbox is a flag, not a second account.

## Verify a webhook

```python
from flask import Flask, request

from cryptunnel import verify_webhook

app = Flask(__name__)
WEBHOOK_SECRET = "<whsec_...>"

@app.post("/cryptunnel")
def callback():
    if not verify_webhook(WEBHOOK_SECRET, request.headers, request.get_data()):
        return "", 401
    payment = request.get_json()
    if payment["status"] in ("confirmed", "confirmed_manual"):
        deliver(payment["external_id"])  # deduplicate on (id, status): retries repeat the same pair
    return "", 200
```

Pass the raw body bytes as received - parsing and re-serialising the JSON changes the signature.
A failed delivery is retried 60 times, once a minute, for one hour, each attempt re-signed with a
fresh timestamp over the same body.

## Async

```python
import asyncio

from cryptunnel import Cryptunnel

async def main():
    async with Cryptunnel("<merchant id>", "<api key>", sandbox=True) as cryptunnel:
        currencies = await cryptunnel.list_currencies()
        payment = await cryptunnel.create_h2h_payment(10, "USD", "order-2", currencies[0]["code"])
        print(payment["wallet_address"], payment["amount"], payment["currency"])

asyncio.run(main())
```

## The whole surface

| Method | Call |
| --- | --- |
| `create_widget_payment(amount, currency, external_id, ...)` | `POST /v1/payments/widget` |
| `create_h2h_payment(amount, currency, external_id, target_currency, ...)` | `POST /v1/payments/h2h` |
| `get_payment(payment_id)` | `GET /v1/payments/{id}` |
| `list_payments(limit, offset)` | `GET /v1/payments` |
| `list_currencies()` | `GET /v1/currencies` |
| `get_merchant()` | `GET /v1/merchants` |
| `verify_webhook(secret, headers, raw_body)` | local, no request |
| `wait_for_payment(payment_id)` | polls `GET /v1/payments/{id}` |

Every method exists on both `Cryptunnel` (await it) and `CryptunnelSync` (call it).

Payment creation is idempotent on `external_id`: a retry after a network timeout returns the payment
you already created instead of a second one. Repeating an `external_id` with a different amount or
currency is rejected with `PAYMENT_ALREADY_EXISTS`.

`get_payment` returns two shapes, and the status tells them apart: a `created` or `expired` payment
carries no `amount`, `currency` or `wallet_address`, because nobody has picked a currency for it
yet. Read them with `payment.get("amount")` rather than `payment["amount"]` unless you already know
the status.

`wait_for_payment` is for scripts and development - it polls every 5 seconds, backing off to 30, and
raises `PaymentTimeoutError` after 30 minutes. In production the webhook is the guarantee: a buyer
who closes the page still produces a callback.

## Errors

```python
from cryptunnel import AuthenticationError, RateLimitError, ValidationError

try:
    cryptunnel.create_h2h_payment(10, "USD", "order-3", "DOGE")
except ValidationError as error:
    print(error.code)  # WALLET_NOT_FOUND - you have no active DOGE wallet
except AuthenticationError:
    print("check the merchant id and the api key")
except RateLimitError as error:
    print(error.retry_after)  # seconds to wait; None when the API sends no Retry-After header
```

`CryptunnelError` is the base; `AuthenticationError` (401), `NotFoundError` (404),
`ValidationError` (400), `RateLimitError` (429) and `ApiError` (5xx and transport failures) derive
from it. The raw API `code` is always on the exception.

## Links

- [Quickstart](https://docs.cryptunnel.io/docs/quickstart) - registration to first payment
- [Sandbox and faucets](https://docs.cryptunnel.io/docs/sandbox) - test coins without spending any
- [API reference](https://docs.cryptunnel.io)
- Support: [GitHub Issues](https://github.com/cryptunnel/cryptunnel-python/issues)

MIT licensed.

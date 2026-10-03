"""Cryptunnel - accept crypto payments straight to your own wallets.

```python
from cryptunnel import CryptunnelSync

cryptunnel = CryptunnelSync("<merchant id>", "<api key>", sandbox=True)
payment = cryptunnel.create_widget_payment(10, "USD", "order-1")
print(payment["url"])
```
"""

from ._version import __version__
from .client import DEFAULT_BASE_URL, TERMINAL_STATUSES, Cryptunnel, CryptunnelSync, user_agent
from .errors import (
    ApiError,
    AuthenticationError,
    CryptunnelError,
    NotFoundError,
    PaymentTimeoutError,
    RateLimitError,
    ValidationError,
)
from .webhooks import verify_webhook

__all__ = [
    "DEFAULT_BASE_URL",
    "TERMINAL_STATUSES",
    "ApiError",
    "AuthenticationError",
    "Cryptunnel",
    "CryptunnelError",
    "CryptunnelSync",
    "NotFoundError",
    "PaymentTimeoutError",
    "RateLimitError",
    "ValidationError",
    "user_agent",
    "verify_webhook",
]

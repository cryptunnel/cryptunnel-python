"""Webhook signature verification - the one part of an integration that must not be hand-rolled."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Mapping

DEFAULT_TOLERANCE = 300


def verify_webhook(
    secret: str,
    headers: Mapping[str, Any],
    raw_body: bytes | str,
    tolerance: int = DEFAULT_TOLERANCE,
) -> bool:
    """Verify a callback signed by Cryptunnel.

    ``raw_body`` must be the bytes as received: parsing and re-serialising the JSON changes the
    signature. Returns False for anything that does not verify - it never raises.
    """
    timestamp = _header(headers, "x-webhook-timestamp")
    signature = _header(headers, "x-webhook-signature")
    if not timestamp or not signature:
        return False

    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False

    if abs(time.time() - sent_at) > tolerance:
        return False

    body = raw_body.encode() if isinstance(raw_body, str) else raw_body
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    # compare_digest is constant time and safe for signatures of the wrong length
    return hmac.compare_digest(expected, signature)


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        # Plain dicts keep the casing the framework handed over
        value = next((v for k, v in headers.items() if k.lower() == name), None)
    if isinstance(value, bytes):
        return value.decode()
    return value if value is None else str(value)

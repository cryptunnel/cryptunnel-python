import hashlib
import hmac
import time

from cryptunnel import verify_webhook

SECRET = "whsec_test"
BODY = b'{"id":"n9cdFaTccYbXecVekHKW8Q","status":"confirmed"}'


def sign(body: bytes, timestamp: int, secret: str = SECRET) -> dict[str, str]:
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return {"x-webhook-timestamp": str(timestamp), "x-webhook-signature": signature}


def test_accepts_a_genuine_callback():
    assert verify_webhook(SECRET, sign(BODY, int(time.time())), BODY) is True


def test_accepts_headers_in_any_casing_and_a_string_body():
    headers = {key.title(): value for key, value in sign(BODY, int(time.time())).items()}
    assert verify_webhook(SECRET, headers, BODY.decode()) is True


def test_rejects_a_tampered_body():
    assert verify_webhook(SECRET, sign(BODY, int(time.time())), BODY + b" ") is False


def test_rejects_a_stale_timestamp():
    assert verify_webhook(SECRET, sign(BODY, int(time.time()) - 301), BODY) is False


def test_accepts_a_stale_timestamp_within_a_wider_tolerance():
    headers = sign(BODY, int(time.time()) - 301)
    assert verify_webhook(SECRET, headers, BODY, tolerance=600) is True


def test_rejects_a_signature_of_the_wrong_length():
    headers = sign(BODY, int(time.time()))
    headers["x-webhook-signature"] = headers["x-webhook-signature"][:10]
    assert verify_webhook(SECRET, headers, BODY) is False


def test_rejects_another_secret():
    assert verify_webhook(SECRET, sign(BODY, int(time.time()), "whsec_other"), BODY) is False


def test_rejects_missing_or_unparsable_headers():
    assert verify_webhook(SECRET, {}, BODY) is False
    headers = sign(BODY, int(time.time()))
    headers["x-webhook-timestamp"] = "not-a-number"
    assert verify_webhook(SECRET, headers, BODY) is False

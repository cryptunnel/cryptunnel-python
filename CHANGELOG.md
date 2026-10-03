# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the package follows semantic versioning.

## [1.1.0] - 2026-10-03

### Added

- Every request carries a `User-Agent` naming the package version, Python, httpx and the platform,
  so Cryptunnel can see which SDK versions are in use. An optional `app="my-shop/2.0"` argument on
  both clients appends your own application to it.
- The version is read from one place (`cryptunnel._version`) and exposed as `cryptunnel.__version__`.

## [1.0.0] - 2026-10-03

### Added

- `Cryptunnel` async client and `CryptunnelSync` blocking mirror over `httpx`.
- Payment creation (widget and h2h), payment read and list, currency list, merchant info.
- `verify_webhook` - constant-time HMAC-SHA256 verification with a timestamp tolerance.
- `wait_for_payment` - polling with exponential backoff for scripts and development.
- Exception hierarchy mapping API status codes, keeping the raw API `code`.
- `sandbox=True` switch marking every created payment as a test payment.

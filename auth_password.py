"""Password hashing utilities — PBKDF2 with legacy plaintext fallback."""

import hashlib
import hmac
import secrets

_HASH_PREFIX = "pbkdf2"
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    )
    return f"{_HASH_PREFIX}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or not stored.startswith(f"{_HASH_PREFIX}$"):
        # Legacy plaintext — constant-time compare against empty-safe strings.
        return hmac.compare_digest(password or "", stored or "")
    try:
        _, salt, expected_hex = stored.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    )
    return hmac.compare_digest(digest.hex(), expected_hex)

"""Password hashing and verification with bcrypt."""

import bcrypt

from app.config import get_settings

# bcrypt only uses the first 72 bytes of its input, so longer passwords are
# rejected instead of being silently truncated.
BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt hash of ``plain_password``, ready to store."""
    password_bytes = plain_password.encode("utf-8")
    if not password_bytes:
        raise ValueError("Password must not be empty")
    if len(password_bytes) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if ``plain_password`` matches the stored ``password_hash``."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Raised for a malformed hash; treat it as "does not match".
        return False

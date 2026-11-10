import pytest

from app.auth.security import BCRYPT_MAX_BYTES, hash_password, verify_password

pytestmark = pytest.mark.unit


def test_hash_is_not_the_plain_password():
    hashed = hash_password("Secret123")
    assert hashed != "Secret123"
    assert hashed.startswith("$2b$")


def test_same_password_gives_different_hashes():
    # A fresh random salt is used every time.
    assert hash_password("Secret123") != hash_password("Secret123")


def test_verify_accepts_correct_password():
    hashed = hash_password("Secret123")
    assert verify_password("Secret123", hashed) is True


@pytest.mark.parametrize("attempt", ["secret123", "Secret1234", "", " Secret123"])
def test_verify_rejects_wrong_password(attempt):
    hashed = hash_password("Secret123")
    assert verify_password(attempt, hashed) is False


def test_verify_returns_false_for_malformed_hash():
    assert verify_password("Secret123", "not-a-bcrypt-hash") is False


def test_hash_rejects_empty_password():
    with pytest.raises(ValueError, match="empty"):
        hash_password("")


def test_hash_rejects_password_longer_than_bcrypt_limit():
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password("A" * (BCRYPT_MAX_BYTES + 1))


def test_hash_handles_unicode_password():
    hashed = hash_password("Pässwörd1")
    assert verify_password("Pässwörd1", hashed)

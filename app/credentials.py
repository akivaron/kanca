"""Encrypt connector credentials before they enter the Kanca database."""
import json
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    key = os.getenv('KANCA_CREDENTIALS_KEY', '')
    if not key:
        raise ValueError('KANCA_CREDENTIALS_KEY is not configured.')
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ValueError('KANCA_CREDENTIALS_KEY must be a Fernet key.') from exc


def encrypt_credentials(credentials: dict) -> str:
    raw = json.dumps(credentials, ensure_ascii=False, separators=(',', ':')).encode()
    return _fernet().encrypt(raw).decode()


def decrypt_credentials(value: str) -> dict:
    try:
        raw = _fernet().decrypt(value.encode())
        result = json.loads(raw)
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Stored ERP credentials could not be decrypted.') from exc
    if not isinstance(result, dict):
        raise ValueError('Stored ERP credentials are invalid.')
    return result

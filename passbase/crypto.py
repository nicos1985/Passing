import logging
from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken
from passing import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Create and return a Fernet instance using configured key.

    Raises RuntimeError if key is not configured or invalid.
    """
    key = getattr(settings, "CRYPTOGRAPHY_KEY", None)
    if not key:
        raise RuntimeError("CRYPTOGRAPHY_KEY is not configured in settings")

    # Ensure bytes
    if isinstance(key, str):
        key_bytes = key.encode()
    else:
        key_bytes = key

    try:
        return Fernet(key_bytes)
    except Exception as exc:
        logger.exception("Invalid CRYPTOGRAPHY_KEY: %s", exc)
        raise RuntimeError("Invalid CRYPTOGRAPHY_KEY") from exc


def encrypt_data(data: Union[str, bytes]) -> str:
    """Encrypt a string/bytes and return the token as a utf-8 string.

    Always returns a textual token (urlsafe base64). Raises RuntimeError on misconfiguration.
    """
    if isinstance(data, str):
        plaintext = data.encode()
    elif isinstance(data, bytes):
        plaintext = data
    else:
        raise TypeError("encrypt_data expects str or bytes")

    f = _get_fernet()
    token = f.encrypt(plaintext)
    return token.decode()


def decrypt_data(token: Union[str, bytes]) -> Optional[str]:
    """Decrypt a token (str or bytes) and return plaintext string.

    Returns None if decryption fails (e.g., invalid token) and logs the event.
    """
    if isinstance(token, str):
        token_bytes = token.encode()
    elif isinstance(token, bytes):
        token_bytes = token
    else:
        raise TypeError("decrypt_data expects str or bytes")

    f = _get_fernet()
    try:
        plaintext = f.decrypt(token_bytes)
        return plaintext.decode()
    except InvalidToken:
        logger.warning("Failed to decrypt token: InvalidToken")
        return None
    except Exception as exc:
        logger.exception("Unexpected error during decrypt_data: %s", exc)
        return None

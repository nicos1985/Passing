"""Fernet helpers compatible with the historical bytes-repr database format."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _token(value):
    if isinstance(value, str):
        if value.startswith("b'") and value.endswith("'"):
            value = value[2:-1]
        return value.encode('utf-8')
    return value


def encrypt_data(data, *, allow_encrypted=False):
    cipher = Fernet(settings.CRYPTOGRAPHY_KEY)
    if allow_encrypted and (isinstance(data, bytes) or (data.startswith("b'") and data.endswith("'"))):
        try:
            cipher.decrypt(_token(data))
            return _token(data)
        except InvalidToken:
            # A password resembling bytes-repr is still a password, not ciphertext.
            pass
    return cipher.encrypt(data.encode('utf-8') if isinstance(data, str) else data)


def decrypt_data(encrypted_data):
    if encrypted_data in ('', b'', None):
        return ''
    try:
        return Fernet(settings.CRYPTOGRAPHY_KEY).decrypt(_token(encrypted_data)).decode('utf-8')
    except (InvalidToken, UnicodeError, TypeError):
        raise ValueError('No se pudo descifrar el registro; verificá la clave y la integridad de los datos.') from None

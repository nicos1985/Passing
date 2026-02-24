import os
import pytest
from django.conf import settings
from cryptography.fernet import Fernet
from passbase.crypto import encrypt_data, decrypt_data
from passbase.models import Contrasena, LogData, SeccionContra
from login.models import CustomUser


def setup_module(module):
    # Ensure a CRYPTOGRAPHY_KEY is present for tests; generate temporary key if missing
    if not os.getenv('CRYPTOGRAPHY_KEY'):
        if getattr(settings, 'CRYPTOGRAPHY_KEY', None):
            key_val = settings.CRYPTOGRAPHY_KEY
            if isinstance(key_val, (bytes, bytearray)):
                os.environ['CRYPTOGRAPHY_KEY'] = key_val.decode()
            else:
                os.environ['CRYPTOGRAPHY_KEY'] = str(key_val)
        else:
            os.environ['CRYPTOGRAPHY_KEY'] = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_encrypt_decrypt_roundtrip():
    plaintext = 's3cr3t-passw0rd!'
    token = encrypt_data(plaintext)
    assert isinstance(token, str) and len(token) > 0

    decrypted = decrypt_data(token)
    assert decrypted == plaintext


@pytest.mark.django_db
def test_contrasena_save_encrypts_and_redacts_log(db):
    # Create a user to own the Contrasena
    user = CustomUser.objects.create(username='testuser', email='test@example.com')
    # Ensure related Seccion exists
    seccion = SeccionContra.objects.create(nombre_seccion='default')

    c = Contrasena(
        nombre_contra='test-entry',
        seccion=seccion,
        link='https://example.test',
        usuario='alice',
        contraseña='P@ssw0rd!',
        info='test info',
        owner=user,
    )
    c.save()

    # Reload from DB
    stored = Contrasena.objects.get(id=c.id)

    # Stored contraseña should not be plaintext when accessed directly
    assert stored.contraseña != 'P@ssw0rd!'

    # get_decrypted_password should return original plaintext
    assert stored.get_decrypted_password() == 'P@ssw0rd!'

    # LogData should have a redacted password
    log = LogData.objects.filter(contraseña=stored.id).first()
    assert log is not None
    assert log.password == '[REDACTED]'


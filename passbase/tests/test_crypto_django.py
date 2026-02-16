from django.test import TestCase
from django.conf import settings
from cryptography.fernet import Fernet
from passbase.crypto import encrypt_data, decrypt_data
from passbase.models import Contrasena, LogData, SeccionContra
from login.models import CustomUser
from django_tenants.utils import get_tenant_model, tenant_context


class CryptoDjangoTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure a valid Fernet key is available in settings for tests
        # Force a valid Fernet key for tests to avoid invalid-key errors from env
        settings.CRYPTOGRAPHY_KEY = Fernet.generate_key()

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = 's3cr3t-passw0rd!'
        token = encrypt_data(plaintext)
        self.assertIsInstance(token, str)

        decrypted = decrypt_data(token)
        self.assertEqual(decrypted, plaintext)

    def test_contrasena_save_encrypts_and_redacts_log(self):
        # Create tenant and switch to its schema so tenant apps' models exist
        TenantModel = get_tenant_model()
        tenant = TenantModel(schema_name='test_schema', client_name='testclient', primary_mail='owner@test.local')
        tenant.save()
        # create domain mapping for the tenant
        tenant.domains.create(domain='test.local', is_primary=True)

        with tenant_context(tenant):
            # Create required related objects inside tenant schema
            user = CustomUser.objects.create(username='testuser', email='test@example.com')
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

            stored = Contrasena.objects.get(id=c.id)

            # Stored contraseña should not equal plaintext
            self.assertNotEqual(stored.contraseña, 'P@ssw0rd!')

            # Decrypt returns original
            self.assertEqual(stored.get_decrypted_password(), 'P@ssw0rd!')

            # Log exists and password is redacted
            log = LogData.objects.filter(contraseña=stored.id).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.password, '[REDACTED]')

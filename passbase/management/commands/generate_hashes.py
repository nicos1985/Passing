from django.core.management.base import BaseCommand
from passbase.crypto import decrypt_data
from passbase.models import Contrasena
import hashlib

class Command(BaseCommand):
    help = 'Genera hashes para todas las contraseñas existentes'

    def handle(self, *args, **kwargs):
        contrasenas = Contrasena.objects.all().order_by('id')
        for contrasena in contrasenas:
        # Sólo procesa si el hash está vacío
            usuario = contrasena.usuario
            password = contrasena.contraseña
            
            # Desencripta el usuario y la contraseña si están encriptados
            try:
                usuario_decrypted = decrypt_data(usuario)
                password_decrypted = decrypt_data(password)
                self.stdout.write(self.style.SUCCESS(f'usuario desencriptado: {password_decrypted} y {usuario_decrypted} '))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error desencriptando para id {contrasena.id}: {e}'))
                continue

            # Genera el hash
            hash_combination = hashlib.sha256((usuario_decrypted + password_decrypted).encode('utf-8')).hexdigest()
            
            contrasena.hash = hash_combination
            contrasena.save()
            self.stdout.write(self.style.SUCCESS(f'Contrasena ID: {contrasena.id}'))
            self.stdout.write(self.style.SUCCESS(f'Hash: {contrasena.hash}'))

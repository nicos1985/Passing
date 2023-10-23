from cryptography.fernet import Fernet
from django.conf import settings

def encrypt_data(data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
    return encrypted_data

def decrypt_data(encrypted_data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    decrypted_data = cipher_suite.decrypt(encrypted_data).decode('utf-8')
    return decrypted_data
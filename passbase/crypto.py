from cryptography.fernet import Fernet, InvalidToken
#from passbase.models import Contrasena
from passing import settings


def encrypt_data(data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    encrypted_data = cipher_suite.encrypt(data.encode())
    return encrypted_data

def decrypt_data(encrypted_data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    if isinstance(encrypted_data, str):
        # Removing the extra characters introduced by string representation
        encrypted_data = encrypted_data[2:-1].encode()  # Convertir a bytes después de eliminar los caracteres extraños
    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_data)
        decrypted_data = decrypted_bytes.decode()
        return decrypted_data
    except Exception as e:
        print(f"Decryption failed: {e}")
        raise e

"""
key = Fernet.generate_key()
print(key)

# PARA HACER PRUEBAS DE ENCRIPTACION

def encrypt_data(data):
    key = settings.CRYPTOGRAPHY_KEY
    print(f'Encryption key: {key}')
    cipher_suite = Fernet(key)
    encrypted_data = cipher_suite.encrypt(data.encode())
    print(f'Encrypted data: {encrypted_data}')
    return encrypted_data

def decrypt_data(encrypted_data):
    key = settings.CRYPTOGRAPHY_KEY
    print(f'Decryption key: {key}')
    cipher_suite = Fernet(key)
    print(f'Encrypted data (before decoding if necessary): {encrypted_data}')
    if isinstance(encrypted_data, str):
        # Removing the extra characters introduced by string representation
        encrypted_data = encrypted_data[2:-1].encode()  # Convertir a bytes después de eliminar los caracteres extraños
    print(f'Encrypted data (bytes): {encrypted_data}')

    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_data)
        print(f'Decrypted bytes : {decrypted_bytes}')
        decrypted_data = decrypted_bytes.decode()
        print(f'Decrypted data : {decrypted_data}')
        return decrypted_data
    except Exception as e:
        print(f"Decryption failed: {e}")
        raise e

# Example usage
try:
    encrypted_text = Contrasena.objects.get(id=45).contraseña
    print(f'encrypted_text from database (raw): {encrypted_text}')
    print(f'Length of encrypted_text: {len(encrypted_text)}')

    # Ensure no extra characters and proper type
    if isinstance(encrypted_text, bytes):
        encrypted_text = encrypted_text.decode('utf-8')  # Convert to string to manipulate
    print(f'Encrypted text after conversion: {encrypted_text}')

    decrypted_text = decrypt_data(encrypted_text)
    print(f'prueba decrypt = {decrypted_text}')
except Contrasena.DoesNotExist:
    print("The Contrasena with id=45 does not exist.")
except Exception as e:
    print(f"An error occurred: {e}")

# Testing with new encryption and decryption
try:
    test_data = 'TestString'
    new_encrypted_data = encrypt_data(test_data)
    print(f'new_encrypted_data = {new_encrypted_data}')
    new_decrypted_data = decrypt_data(new_encrypted_data)
    print(f'new_decrypted_data = {new_decrypted_data}')
except Exception as e:
    print(f"An error occurred during test encryption/decryption: {e}")

    """
from cryptography.fernet import Fernet
from passing import settings


def encrypt_data(data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    encrypted_data = cipher_suite.encrypt(data)
    return encrypted_data

def decrypt_data(encrypted_data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    return decrypted_data


# Generar una clave
key = Fernet.generate_key()
print(f"Clave generada: {key}")

# Guardar la clave en un archivo (como bytes)
#with open("clave.key", "wb") as key_file:
#    key_file.write(key)

# Cargar la clave desde el archivo (como bytes)
#with open("clave.key", "rb") as key_file:
#    key = key_file.read()

# Crear el objeto Fernet con la clave
cipher_suite = Fernet(key)

# Datos a encriptar
data = b"Datos secretos"

# Encriptar los datos
encrypted_data = cipher_suite.encrypt(data)
print(f"Datos encriptados: {encrypted_data}")

# Desencriptar los datos
decrypted_data = cipher_suite.decrypt(encrypted_data)
print(f"Datos desencriptados: {decrypted_data}")

def get_fernet():
    key = settings.CRYPTOGRAPHY_KEY
    print(f"Clave (en bytes): {key}")
    print(f"Longitud de la clave: {len(key)}")
    return Fernet(key)


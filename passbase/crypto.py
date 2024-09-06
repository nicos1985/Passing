from cryptography.fernet import Fernet, InvalidToken
from passing import settings


def encrypt_data(data):
    if data.startswith("b'") and data.endswith("'"):
        return data
    else:
        key = settings.CRYPTOGRAPHY_KEY
        cipher_suite = Fernet(key)
        encrypted_data = cipher_suite.encrypt(data.encode())
        return encrypted_data

def decrypt_data(encrypted_data):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    
    if isinstance(encrypted_data,(str) ):
        if encrypted_data.startswith("b'") and encrypted_data.endswith("'"):
            
            # Removing the extra characters introduced by string representation
            encrypted_data = encrypted_data[2:-1].encode()
        else:
            
            encrypted_data = encrypted_data.encode()

    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_data)
        decrypted_data = decrypted_bytes.decode()
        
        return decrypted_data
    except Exception as e:
        print(f"Error decrypting data: {e}")
        return encrypted_data

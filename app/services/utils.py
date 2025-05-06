from cryptography.fernet import Fernet
from app.config import settings
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib

def get_encryption_key():
    salt = settings.CIPHER.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.CIPHER.encode()))
    return Fernet(key)

def encrypt(data: str) -> str:
    if not data:
        return data
        
    f = get_encryption_key()
    return f.encrypt(data.encode()).decode()

def decrypt(encrypted_data: str) -> str:
    if not encrypted_data:
        return encrypted_data
        
    f = get_encryption_key()
    return f.decrypt(encrypted_data.encode()).decode() 

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
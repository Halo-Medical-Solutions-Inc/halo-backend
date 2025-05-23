from cryptography.fernet import Fernet
from app.config import settings
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib

"""
Utils Service for the Halo Application.

This module provides a centralized utils service for the application.
It includes functionality for encrypting and decrypting data, hashing passwords, and other utility functions.
"""

def get_encryption_key():
    """
    Get the encryption key for the application.
    Args:
        None
    Returns:
        Fernet: The encryption key for the application.
    """
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
    """
    Encrypt the data for the application.

    Args:
        data (str): The data to encrypt.
    Returns:
        str: The encrypted data.
    """
    if not data:
        return data
        
    f = get_encryption_key()
    return f.encrypt(data.encode()).decode()

def decrypt(encrypted_data: str) -> str:
    """
    Decrypt the data for the application.

    Args:
        encrypted_data (str): The data to decrypt.
    Returns:
        str: The decrypted data.
    """
    if not encrypted_data:
        return encrypted_data
        
    f = get_encryption_key()
    return f.decrypt(encrypted_data.encode()).decode() 

def hash_password(password: str) -> str:
    """
    Hash the password for the application.

    Args:
        password (str): The password to hash.
    Returns:
        str: The hashed password.
    """
    return hashlib.sha256(password.encode()).hexdigest()
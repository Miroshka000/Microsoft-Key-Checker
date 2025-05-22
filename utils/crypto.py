import base64
import os
from typing import AnyStr, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_key(password: str, salt: bytes = None) -> bytes:
    
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt_data(data: Union[str, bytes], password: str) -> str:
    
    
    salt = os.urandom(16)
    
    
    key = generate_key(password, salt)
    
    
    fernet = Fernet(key)
    
    
    if isinstance(data, str):
        data = data.encode()
    
    
    encrypted_data = fernet.encrypt(data)
    
    
    result = base64.b64encode(salt + encrypted_data).decode()
    
    return result

def decrypt_data(encrypted_data: str, password: str) -> str:
    
    
    decoded_data = base64.b64decode(encrypted_data.encode())
    
    
    salt = decoded_data[:16]
    encrypted = decoded_data[16:]
    
    
    key = generate_key(password, salt)
    
    
    fernet = Fernet(key)
    
    
    decrypted_data = fernet.decrypt(encrypted).decode()
    
    return decrypted_data

def hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    hash_bytes = kdf.derive(password.encode())
    hash_str = base64.b64encode(hash_bytes).decode()
    
    return hash_str, salt

def verify_password(password: str, hash_str: str, salt: bytes) -> bool:
    
    new_hash, _ = hash_password(password, salt)
    return new_hash == hash_str 
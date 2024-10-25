
from typing import Optional
import base64
from cryptography.fernet import Fernet, InvalidToken
from app.settings.config import settings

# Ініціалізація шифрувальника
key = settings.key_crypto
cipher = Fernet(key)


def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode('utf-8') == s
    except Exception:
        # print(f"Error: Failed to base64 decode {e}")
        return False

async def async_encrypt(data: Optional[str]):
    if data is None:
        return None

    encrypted = cipher.encrypt(data.encode())
    encoded_string = base64.b64encode(encrypted).decode('utf-8')
    return encoded_string

async def async_decrypt(encoded_data: Optional[str]):
    if encoded_data is None:
        return None

    if not is_base64(encoded_data):
        return encoded_data

    try:
        encrypted = base64.b64decode(encoded_data.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted).decode('utf-8')
        return decrypted
    except InvalidToken:
        return None

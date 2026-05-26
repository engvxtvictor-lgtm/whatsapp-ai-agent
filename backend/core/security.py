import os
import json
import base64
from typing import Any, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.system.config import settings

# Ensure the encryption key is a 32‑byte base64 string in .env (ENCRYPTION_KEY)

def _get_aesgcm() -> AESGCM:
    key_bytes = base64.b64decode(settings.ENCRYPTION_KEY)
    if len(key_bytes) != 32:
        raise ValueError("ENCRYPTION_KEY must decode to 32 bytes for AES‑256")
    return AESGCM(key_bytes)

def encrypt_payload(data: Dict[str, Any]) -> str:
    """Encrypt a dictionary and return a base64 string.
    Uses AES‑GCM (nonce = 12 bytes) for authenticated encryption.
    """
    aes = _get_aesgcm()
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()

def decrypt_payload(token: str) -> Dict[str, Any]:
    """Decrypt a base64 token back into a dictionary."""
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    aes = _get_aesgcm()
    plaintext = aes.decrypt(nonce, ct, None)
    return json.loads(plaintext)

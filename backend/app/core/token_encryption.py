"""
AES-256-GCM token encryption helpers.

Used to encrypt OAuth access tokens at rest (OWASP A02).
Each call to encrypt_token generates a fresh random IV — never reuse IVs with GCM.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_token(plaintext: str, key_hex: str) -> tuple[str, str]:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns a tuple of (ciphertext_b64, iv_b64). Both values must be stored
    together; the IV is not secret but must be unique per encryption.
    """
    key = bytes.fromhex(key_hex)
    iv = os.urandom(12)  # 96-bit nonce — recommended for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
    return base64.b64encode(ciphertext).decode(), base64.b64encode(iv).decode()


def decrypt_token(ciphertext_b64: str, iv_b64: str, key_hex: str) -> str:
    """Decrypt a value previously encrypted with *encrypt_token*.

    Raises ``cryptography.exceptions.InvalidTag`` if the ciphertext or key
    is invalid (i.e. tampered or wrong key).
    """
    key = bytes.fromhex(key_hex)
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, None).decode()

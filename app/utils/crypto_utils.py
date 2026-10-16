from __future__ import annotations
 
import base64
import binascii
import hmac
import os
import sys
 
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import LEDGER_PASSPHRASE, CRYPTO_KEY
 
# Hard-coded passphrase the decrypted value is compared against.
PASSPHRASE = LEDGER_PASSPHRASE
 
NONCE_SIZE = 12  # bytes, standard for GCM
 
 
# Hard-coded AES-256 key (base64 of 32 random bytes).
# TODO: move to configuration / environment later.
AES_KEY_B64 = CRYPTO_KEY
 
 
def _get_key() -> bytes:
    key = base64.b64decode(AES_KEY_B64)
    if len(key) != 32:
        raise RuntimeError("AES_KEY_B64 must decode to exactly 32 bytes (AES-256)")
    return key
 
 
def encrypt_passphrase(plain_text: str) -> str:
    """Encrypt text and return a base64 token. Mainly for tests / client reference."""
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(_get_key()).encrypt(nonce, plain_text.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")
 
 
def decrypt_passphrase(token: str) -> str:
    """Decrypt a base64 token. Raises ValueError if it is malformed or tampered with."""
    try:
        raw = base64.b64decode(token, validate=True)
        nonce, ciphertext = raw[:NONCE_SIZE], raw[NONCE_SIZE:]
        return AESGCM(_get_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
    except (binascii.Error, InvalidTag, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid encrypted passphrase") from exc
 
 
def verify_passphrase(token: str) -> bool:
    """True if the token decrypts to the hard-coded passphrase."""
    try:
        decrypted = decrypt_passphrase(token)
    except ValueError:
        return False
    # Constant-time comparison avoids leaking info through timing
    return hmac.compare_digest(decrypted.encode("utf-8"), PASSPHRASE.encode("utf-8"))

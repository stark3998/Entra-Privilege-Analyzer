from __future__ import annotations

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings

logger = logging.getLogger(__name__)

_VERSION_PREFIX = "v1:"


class CryptoService:
    """AES-256-GCM encryption for storing secrets in Cosmos DB."""

    def __init__(self, settings: Settings) -> None:
        raw_key = settings.encryption_key
        if not raw_key:
            raise RuntimeError(
                "ENCRYPTION_KEY is not configured — "
                "set it in env vars or Key Vault"
            )
        key_bytes = base64.b64decode(raw_key)
        if len(key_bytes) != 32:
            raise RuntimeError(
                f"ENCRYPTION_KEY must be 32 bytes (base64-encoded); got {len(key_bytes)}"
            )
        self._aesgcm = AESGCM(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string. Returns a versioned, base64-encoded ciphertext."""
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        payload = base64.b64encode(nonce + ct).decode()
        return f"{_VERSION_PREFIX}{payload}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a versioned ciphertext string back to plaintext."""
        if not ciphertext.startswith(_VERSION_PREFIX):
            raise ValueError("Unsupported ciphertext version")
        raw = base64.b64decode(ciphertext[len(_VERSION_PREFIX):])
        nonce = raw[:12]
        ct = raw[12:]
        return self._aesgcm.decrypt(nonce, ct, None).decode()

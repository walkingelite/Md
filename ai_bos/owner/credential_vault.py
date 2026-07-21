"""Credential vault — credentials never stored in the database.

Credentials are referenced by UUID in the database.
Actual values are stored in an encrypted secrets manager.
This module provides the interface; production wires it to
HashiCorp Vault or AWS Secrets Manager.
"""

from __future__ import annotations

import base64
import json
import uuid
from cryptography.fernet import Fernet

from ai_bos.config import settings
from ai_bos.logging_config import log


def _fernet() -> Fernet:
    key = settings.encryption_key.get_secret_value()
    # Key must be 32 url-safe base64-encoded bytes
    return Fernet(key.encode() if len(key) == 44 else base64.urlsafe_b64encode(key.encode()[:32]))


class CredentialVault:
    """Simple encrypted credential store backed by the encryption key.
    Production: swap _store dict for Vault/Secrets Manager calls."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}  # ref_id -> encrypted blob

    def store(self, credential: dict) -> str:
        """Encrypt and store a credential. Returns a reference UUID."""
        ref_id = str(uuid.uuid4())
        payload = json.dumps(credential).encode()
        encrypted = _fernet().encrypt(payload)
        self._store[ref_id] = encrypted
        log.info("vault.stored", ref_id=ref_id, keys=list(credential.keys()))
        return ref_id

    def retrieve(self, ref_id: str) -> dict:
        encrypted = self._store.get(ref_id)
        if not encrypted:
            raise KeyError(f"No credential for ref_id: {ref_id}")
        payload = _fernet().decrypt(encrypted)
        return json.loads(payload.decode())

    def delete(self, ref_id: str) -> None:
        self._store.pop(ref_id, None)
        log.info("vault.deleted", ref_id=ref_id)


vault = CredentialVault()

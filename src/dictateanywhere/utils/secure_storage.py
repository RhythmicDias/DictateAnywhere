"""
Secure credential storage using the OS keychain.

On Windows this maps to the Windows Credential Manager (DPAPI-encrypted).
The Azure Speech API key is NEVER stored in config.json or on disk in plain text.
"""

from __future__ import annotations

import logging
from typing import Optional

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

_SERVICE = "DictateAnywhere"

# Credential identifiers
AZURE_SPEECH_KEY = "azure_speech_api_key"


class SecureStorage:
    """Thin wrapper around keyring for named credential storage."""

    def __init__(self, service: str = _SERVICE) -> None:
        self._service = service

    # ── Generic helpers ───────────────────────────────────────────────────────

    def store(self, credential_id: str, value: str) -> bool:
        """Store *value* under *credential_id*. Returns True on success."""
        if not value or not value.strip():
            logger.warning("Refusing to store empty credential: %s", credential_id)
            return False
        try:
            keyring.set_password(self._service, credential_id, value.strip())
            logger.info("Credential stored: %s", credential_id)
            return True
        except keyring.errors.KeyringError as exc:
            logger.error("Failed to store credential %r: %s", credential_id, exc)
            return False

    def retrieve(self, credential_id: str) -> Optional[str]:
        """Return the stored value for *credential_id*, or None if not found."""
        try:
            value = keyring.get_password(self._service, credential_id)
            return value
        except keyring.errors.KeyringError as exc:
            logger.error("Failed to retrieve credential %r: %s", credential_id, exc)
            return None

    def delete(self, credential_id: str) -> bool:
        """Delete credential. Returns True if deleted, False if not found."""
        try:
            keyring.delete_password(self._service, credential_id)
            logger.info("Credential deleted: %s", credential_id)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
        except keyring.errors.KeyringError as exc:
            logger.error("Failed to delete credential %r: %s", credential_id, exc)
            return False

    def exists(self, credential_id: str) -> bool:
        return self.retrieve(credential_id) is not None

    # ── Named helpers — Azure ─────────────────────────────────────────────────

    def store_azure_key(self, api_key: str) -> bool:
        return self.store(AZURE_SPEECH_KEY, api_key)

    def get_azure_key(self) -> Optional[str]:
        return self.retrieve(AZURE_SPEECH_KEY)

    def delete_azure_key(self) -> bool:
        return self.delete(AZURE_SPEECH_KEY)

    def has_azure_key(self) -> bool:
        return self.exists(AZURE_SPEECH_KEY)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def test_keyring(self) -> bool:
        """Verify the keyring backend works. Returns True if writable."""
        _test_id = "__da_test__"
        _test_val = "ok"
        try:
            keyring.set_password(self._service, _test_id, _test_val)
            result = keyring.get_password(self._service, _test_id)
            keyring.delete_password(self._service, _test_id)
            return result == _test_val
        except Exception as exc:
            logger.error("Keyring backend test failed: %s", exc)
            return False

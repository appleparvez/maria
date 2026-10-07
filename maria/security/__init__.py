"""MARIA Security Layer — credentials, permissions, and audit logging."""

from maria.security.credentials import (
    CredentialVault,
    InvalidCredentialNameError,
    VaultCorruptedError,
    VaultError,
    VaultKeyError,
    derive_key_from_passphrase,
    generate_vault_key,
)

__all__ = [
    "CredentialVault",
    "InvalidCredentialNameError",
    "VaultCorruptedError",
    "VaultError",
    "VaultKeyError",
    "derive_key_from_passphrase",
    "generate_vault_key",
]

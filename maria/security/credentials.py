"""MARIA secure Credential Vault.

Provides authenticated encryption at rest for API keys and secrets using Fernet
(AES-128 in CBC mode with HMAC-SHA256 authentication).
Credentials are never stored or logged in plaintext.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import SecretStr

# Valid credential names: alphanumeric, underscore, hyphen, dot (1-128 chars)
_CREDENTIAL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")
_PBKDF2_ITERATIONS = 100_000
_SALT_SIZE_BYTES = 16


class VaultError(Exception):
    """Base exception for all credential vault errors."""


class VaultCorruptedError(VaultError):
    """Raised when vault data cannot be decrypted or is corrupted."""


class VaultKeyError(VaultError):
    """Raised when an encryption key is invalid or cannot be derived."""


class InvalidCredentialNameError(VaultError):
    """Raised when an invalid credential name is provided."""


def _secure_file_permissions(path: Path) -> None:
    """Apply restrictive read/write permissions to a sensitive file (owner only)."""
    with contextlib.suppress(OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    if os.name == "nt":
        icacls = shutil.which("icacls")
        username = os.environ.get("USERNAME")
        if icacls and username:
            with contextlib.suppress(OSError):
                subprocess.run(  # noqa: S603
                    [icacls, str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
                    capture_output=True,
                    check=False,
                )


def derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """Derive a URL-safe base64-encoded 32-byte Fernet key from a passphrase and salt."""
    if not passphrase:
        msg = "Passphrase cannot be empty."
        raise VaultKeyError(msg)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def generate_vault_key() -> bytes:
    """Generate a cryptographically secure random Fernet key."""
    return Fernet.generate_key()


class CredentialVault:
    """Secure encrypted storage for API keys and credentials.

    - Uses Fernet authenticated encryption (AES-128-CBC + HMAC-SHA256).
    - Writes updates atomically to prevent corruption on interruption.
    - Sets restrictive file permissions (owner read/write only).
    - Masks secret values using pydantic.SecretStr upon retrieval.
    """

    def __init__(
        self,
        vault_path: Path | str | None = None,
        key: bytes | str | SecretStr | None = None,
        key_path: Path | str | None = None,
        salt_path: Path | str | None = None,
    ) -> None:
        """Initialize the CredentialVault.

        Args:
            vault_path: Path to the encrypted credentials file.
                        Defaults to ~/.maria/credentials.enc.
            key: Optional explicit Fernet key or passphrase.
            key_path: Path to stored encryption key file if key is not passed.
                      Defaults to ~/.maria/credentials.key.
            salt_path: Path to stored salt file for passphrase derivation.
                       Defaults to ~/.maria/vault.salt.
        """
        # Late import to prevent circular dependency with maria.config
        from maria.config import get_settings

        settings = get_settings()

        self.vault_path = (
            Path(vault_path).expanduser()
            if vault_path is not None
            else settings.data_dir / "credentials.enc"
        )
        self.key_path = (
            Path(key_path).expanduser()
            if key_path is not None
            else self.vault_path.parent / "credentials.key"
        )
        self.salt_path = (
            Path(salt_path).expanduser()
            if salt_path is not None
            else self.vault_path.parent / "vault.salt"
        )

        # Ensure directory exists with owner permissions
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            self.vault_path.parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        self._fernet = self._initialize_fernet(key, settings.master_key)

    def _initialize_fernet(
        self,
        key: bytes | str | SecretStr | None,
        config_master_key: SecretStr | None,
    ) -> Fernet:
        """Resolve or generate the Fernet encryption cipher."""
        raw_key: bytes | str | None = None

        if isinstance(key, SecretStr):
            raw_key = key.get_secret_value()
        elif key is not None:
            raw_key = key
        elif config_master_key is not None:
            raw_key = config_master_key.get_secret_value()

        if raw_key is not None:
            fernet_key = self._resolve_raw_key(raw_key)
        else:
            fernet_key = self._load_or_generate_key_file()

        try:
            return Fernet(fernet_key)
        except Exception as exc:
            msg = "Failed to initialize encryption cipher with provided key."
            raise VaultKeyError(msg) from exc

    def _resolve_raw_key(self, raw: bytes | str) -> bytes:
        """Convert a user-supplied key or passphrase into a valid Fernet key."""
        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw

        # Check if already a valid Fernet key (44 base64 URL-safe bytes decoding to 32 bytes)
        if len(raw_bytes) == 44:
            with contextlib.suppress(ValueError, binascii.Error):
                decoded = base64.urlsafe_b64decode(raw_bytes)
                if len(decoded) == 32:
                    return raw_bytes

        # Otherwise treat as a passphrase and derive via PBKDF2
        salt = self._load_or_create_salt()
        passphrase_str = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return derive_key_from_passphrase(passphrase_str, salt)

    def _load_or_create_salt(self) -> bytes:
        """Load an existing salt or generate and persist a new one."""
        if self.salt_path.exists():
            try:
                return self.salt_path.read_bytes()
            except OSError as exc:
                msg = f"Cannot read salt file at {self.salt_path}"
                raise VaultKeyError(msg) from exc

        salt = os.urandom(_SALT_SIZE_BYTES)
        try:
            self.salt_path.write_bytes(salt)
            _secure_file_permissions(self.salt_path)
            return salt
        except OSError as exc:
            msg = f"Cannot write salt file at {self.salt_path}"
            raise VaultKeyError(msg) from exc

    def _load_or_generate_key_file(self) -> bytes:
        """Load key from key_path, or generate and persist a new random key."""
        if self.key_path.exists():
            try:
                key_bytes = self.key_path.read_bytes().strip()
                if len(key_bytes) == 44:
                    return key_bytes
                msg = f"Key file at {self.key_path} is invalid."
                raise VaultKeyError(msg)
            except OSError as exc:
                msg = f"Cannot read key file at {self.key_path}"
                raise VaultKeyError(msg) from exc

        # Generate new random Fernet key
        new_key = generate_vault_key()
        try:
            self.key_path.write_bytes(new_key)
            _secure_file_permissions(self.key_path)
            return new_key
        except OSError as exc:
            msg = f"Cannot persist generated key to {self.key_path}"
            raise VaultKeyError(msg) from exc

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate credential name formatting."""
        if not isinstance(name, str) or not _CREDENTIAL_NAME_PATTERN.match(name.strip()):
            msg = (
                f"Invalid credential name '{name}'. Names must be 1-128 alphanumeric "
                "characters, dots, hyphens, or underscores."
            )
            raise InvalidCredentialNameError(msg)

    def _read_data(self) -> dict[str, str]:
        """Read and decrypt all credentials from disk."""
        if not self.vault_path.exists():
            return {}

        try:
            ciphertext = self.vault_path.read_bytes()
        except OSError as exc:
            msg = f"Failed to read vault file at {self.vault_path}"
            raise VaultError(msg) from exc

        if not ciphertext:
            return {}

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            msg = (
                f"Vault file at {self.vault_path} is corrupted, tampered with, "
                "or encryption key is incorrect."
            )
            raise VaultCorruptedError(msg) from exc

        try:
            data = json.loads(decrypted_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                msg = "Decrypted vault data is not a valid JSON dictionary."
                raise VaultCorruptedError(msg)
            return data
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            msg = "Failed to parse decrypted vault data as JSON."
            raise VaultCorruptedError(msg) from exc

    def _write_data(self, data: dict[str, str]) -> None:
        """Encrypt and atomically persist credentials to disk."""
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ciphertext = self._fernet.encrypt(json_bytes)

        # Atomic write: write to temp file in same directory, then atomic rename
        temp_file = self.vault_path.with_name(f"{self.vault_path.name}.tmp")
        try:
            temp_file.write_bytes(ciphertext)
            _secure_file_permissions(temp_file)
            os.replace(temp_file, self.vault_path)
            _secure_file_permissions(self.vault_path)
        except OSError as exc:
            if temp_file.exists():
                with contextlib.suppress(OSError):
                    temp_file.unlink()
            msg = f"Failed to atomically write vault file to {self.vault_path}"
            raise VaultError(msg) from exc

    def set(self, name: str, value: str | SecretStr) -> None:
        """Store a named credential in the vault.

        Args:
            name: Credential identifier (e.g. 'gemini_api_key', 'openai_api_key').
            value: Secret credential value to encrypt.
        """
        self._validate_name(name)
        if isinstance(value, SecretStr):
            secret_value = value.get_secret_value()
        elif isinstance(value, str):
            secret_value = value
        else:
            msg = "Credential value must be a str or SecretStr."
            raise ValueError(msg)

        data = self._read_data()
        data[name] = secret_value
        self._write_data(data)

    def get(self, name: str) -> SecretStr | None:
        """Retrieve a credential wrapped in SecretStr.

        Args:
            name: Credential identifier.

        Returns:
            SecretStr if found, None otherwise.
        """
        self._validate_name(name)
        data = self._read_data()
        val = data.get(name)
        if val is None:
            return None
        return SecretStr(val)

    def get_raw(self, name: str) -> str | None:
        """Retrieve the plaintext credential string.

        Args:
            name: Credential identifier.

        Returns:
            Plaintext string if found, None otherwise.
        """
        secret = self.get(name)
        return secret.get_secret_value() if secret is not None else None

    def has(self, name: str) -> bool:
        """Check if a credential exists in the vault."""
        self._validate_name(name)
        data = self._read_data()
        return name in data

    def delete(self, name: str) -> bool:
        """Delete a named credential from the vault.

        Args:
            name: Credential identifier.

        Returns:
            True if the credential existed and was deleted, False if not found.
        """
        self._validate_name(name)
        data = self._read_data()
        if name not in data:
            return False

        del data[name]
        self._write_data(data)
        return True

    def list_keys(self) -> list[str]:
        """List all stored credential names (never exposes values)."""
        data = self._read_data()
        return sorted(data.keys())

    def clear(self) -> None:
        """Remove all credentials from the vault."""
        self._write_data({})

    def count(self) -> int:
        """Return the number of stored credentials."""
        return len(self.list_keys())

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def __repr__(self) -> str:
        """Safe representation without exposing keys or contents."""
        return f"<CredentialVault path='{self.vault_path}' credentials={self.count()}>"

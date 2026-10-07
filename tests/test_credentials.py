"""Unit tests for the MARIA secure Credential Vault."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from maria.security.credentials import (
    CredentialVault,
    InvalidCredentialNameError,
    VaultCorruptedError,
    VaultKeyError,
    derive_key_from_passphrase,
    generate_vault_key,
)


@pytest.fixture
def vault_dir(tmp_path):
    """Provide a dedicated directory for temporary vault files."""
    return tmp_path / "vault_test"


@pytest.fixture
def test_key():
    """Generate a test Fernet key."""
    return generate_vault_key()


def test_vault_crud_operations(vault_dir, test_key):
    """Verify basic CRUD operations: set, get, has, delete, list_keys."""
    vault_file = vault_dir / "credentials.enc"
    vault = CredentialVault(vault_path=vault_file, key=test_key)

    assert len(vault) == 0
    assert vault.list_keys() == []

    # Set credentials
    vault.set("gemini_api_key", "test-gemini-secret-12345")
    vault.set("openai_api_key", "test-openai-secret-67890")

    assert len(vault) == 2
    assert "gemini_api_key" in vault
    assert "openai_api_key" in vault
    assert "anthropic_api_key" not in vault
    assert vault.list_keys() == ["gemini_api_key", "openai_api_key"]

    # Get credentials (wrapped in SecretStr)
    gem_secret = vault.get("gemini_api_key")
    assert gem_secret is not None
    assert isinstance(gem_secret, SecretStr)
    assert gem_secret.get_secret_value() == "test-gemini-secret-12345"

    # Get raw string
    assert vault.get_raw("openai_api_key") == "test-openai-secret-67890"

    # Non-existent credential
    assert vault.get("missing_key") is None
    assert vault.get_raw("missing_key") is None

    # Delete credential
    assert vault.delete("gemini_api_key") is True
    assert "gemini_api_key" not in vault
    assert len(vault) == 1
    assert vault.delete("non_existent_key") is False


def test_credentials_are_encrypted_at_rest(vault_dir, test_key):
    """Verify that stored credentials NEVER appear as plaintext on disk."""
    secret_value = "super-confidential-api-token-998877"
    vault_file = vault_dir / "credentials.enc"
    vault = CredentialVault(vault_path=vault_file, key=test_key)

    vault.set("test_provider", secret_value)

    # Read raw bytes stored on disk
    raw_disk_bytes = vault_file.read_bytes()

    # Plaintext MUST NOT be found anywhere in the encrypted file
    assert secret_value.encode("utf-8") not in raw_disk_bytes
    assert b"test-provider" not in raw_disk_bytes

    # Ensure disk content is valid Fernet ciphertext
    fernet = Fernet(test_key)
    decrypted = fernet.decrypt(raw_disk_bytes)
    assert secret_value.encode("utf-8") in decrypted


def test_set_with_secret_str(vault_dir, test_key):
    """Verify storing a SecretStr object directly."""
    vault = CredentialVault(vault_path=vault_dir / "credentials.enc", key=test_key)
    secret = SecretStr("secret-from-secretstr")

    vault.set("service_token", secret)
    retrieved = vault.get("service_token")
    assert retrieved is not None
    assert retrieved.get_secret_value() == "secret-from-secretstr"


def test_key_auto_generation_and_persistence(vault_dir):
    """If no key is provided, vault generates and persists a key file."""
    vault_file = vault_dir / "credentials.enc"
    key_file = vault_dir / "custom.key"

    assert not key_file.exists()

    vault = CredentialVault(vault_path=vault_file, key_path=key_file)
    vault.set("auto_key_secret", "stored-value-111")

    # Key file should now exist
    assert key_file.exists()
    assert len(key_file.read_bytes().strip()) == 44

    # Another instance using the same key_file can read data
    vault2 = CredentialVault(vault_path=vault_file, key_path=key_file)
    assert vault2.get_raw("auto_key_secret") == "stored-value-111"


def test_passphrase_key_derivation(vault_dir):
    """Verify that user passphrases derive deterministic keys using PBKDF2."""
    vault_file = vault_dir / "credentials.enc"
    salt_file = vault_dir / "vault.salt"
    passphrase = "my-secure-master-passphrase"

    vault1 = CredentialVault(
        vault_path=vault_file,
        key=passphrase,
        salt_path=salt_file,
    )
    vault1.set("derived_secret", "passphrase-encrypted-data")

    # Second instance with same passphrase and salt file must decrypt correctly
    vault2 = CredentialVault(
        vault_path=vault_file,
        key=passphrase,
        salt_path=salt_file,
    )
    assert vault2.get_raw("derived_secret") == "passphrase-encrypted-data"

    # Second instance with WRONG passphrase must raise VaultCorruptedError
    vault_wrong = CredentialVault(
        vault_path=vault_file,
        key="wrong-passphrase",
        salt_path=salt_file,
    )
    with pytest.raises(VaultCorruptedError):
        vault_wrong.get("derived_secret")


def test_tampered_vault_file_raises_corrupted(vault_dir, test_key):
    """Tampering with vault ciphertext must raise VaultCorruptedError."""
    vault_file = vault_dir / "credentials.enc"
    vault = CredentialVault(vault_path=vault_file, key=test_key)
    vault.set("test_key", "secret-payload")

    # Corrupt the ciphertext
    data = bytearray(vault_file.read_bytes())
    data[15] ^= 0xFF  # Flip bits in Fernet payload
    vault_file.write_bytes(bytes(data))

    with pytest.raises(VaultCorruptedError):
        vault.get("test_key")


def test_invalid_credential_names(vault_dir, test_key):
    """Credential names must adhere to safe naming standards."""
    vault = CredentialVault(vault_path=vault_dir / "credentials.enc", key=test_key)

    with pytest.raises(InvalidCredentialNameError):
        vault.set("", "val")

    with pytest.raises(InvalidCredentialNameError):
        vault.set("invalid/name/path", "val")

    with pytest.raises(InvalidCredentialNameError):
        vault.set("key with spaces", "val")

    with pytest.raises(InvalidCredentialNameError):
        vault.get("bad name!")

    with pytest.raises(InvalidCredentialNameError):
        vault.delete("..\\traversal")


def test_clear_and_empty_vault(vault_dir, test_key):
    """Verify clearing the vault."""
    vault = CredentialVault(vault_path=vault_dir / "credentials.enc", key=test_key)
    vault.set("k1", "v1")
    vault.set("k2", "v2")
    assert len(vault) == 2

    vault.clear()
    assert len(vault) == 0
    assert vault.list_keys() == []


def test_empty_passphrase_raises():
    """Empty passphrase for key derivation should raise VaultKeyError."""
    with pytest.raises(VaultKeyError):
        derive_key_from_passphrase("", b"16_bytes_of_salt_")


def test_safe_repr(vault_dir, test_key):
    """__repr__ must not leak keys or secret values."""
    vault = CredentialVault(vault_path=vault_dir / "credentials.enc", key=test_key)
    vault.set("sensitive_key_name", "sensitive_secret_value")

    representation = repr(vault)
    assert "sensitive_secret_value" not in representation
    assert "credentials=1" in representation

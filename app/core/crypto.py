import base64
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_public_key,
)

from app.core.config import settings


def generate_salt(length: int = 16) -> str:
    """Generate cryptographically secure random salt in base64."""
    return base64.b64encode(os.urandom(length)).decode("utf-8")


def generate_x25519_keypair() -> tuple[x25519.X25519PrivateKey, str]:
    """Generate an X25519 private key and its raw base64 public key."""
    private_key = x25519.X25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_bytes).decode("utf-8")
    return private_key, public_key_b64


def derive_shared_secret(private_key: x25519.X25519PrivateKey, peer_public_key_b64: str) -> bytes:
    """Compute ECDH shared secret using local private key and peer's base64 public key."""
    peer_pub_bytes = base64.b64decode(peer_public_key_b64)
    peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
    return private_key.exchange(peer_public_key)


def derive_key_hkdf(shared_secret: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """Derive a fixed-length symmetric key from a shared secret using HKDF SHA-256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    )
    return hkdf.derive(shared_secret)


def derive_user_master_key(password: str, salt_b64: str) -> bytes:
    """Derive 256-bit User Master Key from password and salt using PBKDF2-HMAC-SHA256."""
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_aes_gcm(key: bytes, plaintext: bytes) -> tuple[str, str]:
    """Encrypt plaintext using AES-256-GCM with a random 12-byte nonce.
    
    Returns (ciphertext_b64, nonce_b64).
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return (
        base64.b64encode(ciphertext).decode("utf-8"),
        base64.b64encode(nonce).decode("utf-8"),
    )


def decrypt_aes_gcm(key: bytes, ciphertext_b64: str, nonce_b64: str) -> bytes:
    """Decrypt ciphertext using AES-256-GCM.
    
    Raises cryptography.exceptions.InvalidTag if tampered or incorrect key.
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _get_server_master_key() -> bytes:
    """Derive a 256-bit server key from settings.JWT_SECRET_KEY."""
    return derive_key_hkdf(
        shared_secret=settings.JWT_SECRET_KEY.encode("utf-8"),
        salt=b"traffic-server-master-salt",
        info=b"server-secret-envelope",
        length=32,
    )


def encrypt_server_secret(secret_data: bytes) -> tuple[str, str]:
    """Encrypt sensitive internal data (e.g. session keys) using the server master key."""
    master_key = _get_server_master_key()
    return encrypt_aes_gcm(master_key, secret_data)


def decrypt_server_secret(ciphertext_b64: str, nonce_b64: str) -> bytes:
    """Decrypt internal data using the server master key."""
    master_key = _get_server_master_key()
    return decrypt_aes_gcm(master_key, ciphertext_b64, nonce_b64)

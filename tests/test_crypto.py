import pytest
from cryptography.exceptions import InvalidTag
from app.core.crypto import (
    generate_x25519_keypair,
    derive_shared_secret,
    derive_key_hkdf,
    derive_user_master_key,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
    encrypt_server_secret,
    decrypt_server_secret,
    generate_salt,
)

def test_x25519_keypair_and_shared_secret():
    alice_priv, alice_pub_b64 = generate_x25519_keypair()
    bob_priv, bob_pub_b64 = generate_x25519_keypair()

    assert alice_pub_b64 != bob_pub_b64

    shared_alice = derive_shared_secret(alice_priv, bob_pub_b64)
    shared_bob = derive_shared_secret(bob_priv, alice_pub_b64)

    assert shared_alice == shared_bob
    assert len(shared_alice) == 32

def test_derive_key_hkdf():
    shared_secret = b"\x01" * 32
    salt = b"test-salt"
    info = b"chat-payload-encryption"

    key1 = derive_key_hkdf(shared_secret, salt, info, length=32)
    key2 = derive_key_hkdf(shared_secret, salt, info, length=32)

    assert key1 == key2
    assert len(key1) == 32

def test_derive_user_master_key():
    salt = generate_salt()
    key1 = derive_user_master_key("my-secret-password", salt)
    key2 = derive_user_master_key("my-secret-password", salt)
    key3 = derive_user_master_key("wrong-password", salt)

    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 32

def test_aes_gcm_encrypt_decrypt_roundtrip():
    key = b"\x02" * 32
    plaintext = b"Hello, this is a secret E2E message!"

    ciphertext_b64, nonce_b64 = encrypt_aes_gcm(key, plaintext)

    decrypted = decrypt_aes_gcm(key, ciphertext_b64, nonce_b64)
    assert decrypted == plaintext

def test_aes_gcm_tampered_ciphertext_fails():
    key = b"\x02" * 32
    plaintext = b"Tamper test"
    ciphertext_b64, nonce_b64 = encrypt_aes_gcm(key, plaintext)

    # Tamper with the ciphertext
    import base64
    raw_ct = bytearray(base64.b64decode(ciphertext_b64))
    raw_ct[0] ^= 0xFF
    tampered_b64 = base64.b64encode(raw_ct).decode("utf-8")

    with pytest.raises(InvalidTag):
        decrypt_aes_gcm(key, tampered_b64, nonce_b64)

def test_server_secret_encryption_roundtrip():
    secret_bytes = b"ephemeral-session-key-32-bytes!!"
    enc_b64, nonce_b64 = encrypt_server_secret(secret_bytes)

    recovered = decrypt_server_secret(enc_b64, nonce_b64)
    assert recovered == secret_bytes

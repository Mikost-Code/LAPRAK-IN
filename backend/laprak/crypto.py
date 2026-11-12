"""Envelope encryption for per-user secrets.

master key (server env) -> wraps one random data key per user -> encrypts each API key.
Rotating the master key only requires re-wrapping data keys, never touching stored secrets.
"""
from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _seal(key: bytes, plaintext: bytes, aad: bytes) -> str:
    nonce = os.urandom(12)
    return base64.b64encode(nonce + AESGCM(key).encrypt(nonce, plaintext, aad)).decode()


def _open(key: bytes, token: str, aad: bytes) -> bytes:
    raw = base64.b64decode(token)
    return AESGCM(key).decrypt(raw[:12], raw[12:], aad)


def new_wrapped_data_key(master: bytes, user_id: str) -> str:
    return _seal(master, os.urandom(32), user_id.encode())


def unwrap_data_key(master: bytes, wrapped: str, user_id: str) -> bytes:
    try:
        return _open(master, wrapped, user_id.encode())
    except (InvalidTag, ValueError) as error:
        raise ValueError("Kunci data pengguna tidak dapat dibuka; master key berubah?") from error


def encrypt_secret(data_key: bytes, secret: str, profile_id: str) -> str:
    return _seal(data_key, secret.encode(), profile_id.encode()) if secret else ""


def decrypt_secret(data_key: bytes, token: str, profile_id: str) -> str:
    if not token:
        return ""
    try:
        return _open(data_key, token, profile_id.encode()).decode()
    except (InvalidTag, ValueError) as error:
        raise ValueError("API key tersimpan tidak dapat didekripsi.") from error

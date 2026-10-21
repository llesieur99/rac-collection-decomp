"""The cipher operations the SELF decryptor needs.

The SELF container of a retail PlayStation 3 program protects its metadata
with **AES-256-CBC** and its sections with **AES-128-CTR**.  The AES-128
keystream already lives in [`aes.py`](aes.py); this module adds the AES-256
width, the inverse cipher, and the CBC mode.

The tool falls back on the ``cryptography`` package when it is installed,
because it is orders of magnitude faster, and on the pure Python
implementation otherwise.  Both paths are checked against each other by the
unit tests.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aes import RCON, SBOX  # noqa: E402

# The inverse substitution box, built from the forward one.
INV_SBOX = bytes(SBOX.index(i) for i in range(256))

BLOCK = 16


def _xtime(a: int) -> int:
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1B) & 0xFF
    return a


def _mul(a: int, b: int) -> int:
    out = 0
    for _ in range(8):
        if b & 1:
            out ^= a
        b >>= 1
        a = _xtime(a)
    return out


def expand_key_256(key: bytes) -> list[list[int]]:
    """Return the fifteen AES-256 round keys as lists of sixteen bytes."""
    if len(key) != 32:
        raise ValueError("AES-256 needs a 32-byte key")
    words = [list(key[i * 4:i * 4 + 4]) for i in range(8)]
    for i in range(8, 60):
        temp = list(words[i - 1])
        if i % 8 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= RCON[i // 8 - 1]
        elif i % 8 == 4:
            temp = [SBOX[b] for b in temp]
        words.append([a ^ b for a, b in zip(words[i - 8], temp)])
    return [sum(words[r * 4:r * 4 + 4], []) for r in range(15)]


def _add_round_key(state: list[int], key: list[int]) -> list[int]:
    return [b ^ k for b, k in zip(state, key)]


def _shift_rows(state: list[int]) -> list[int]:
    # The state is column major: the byte of row r, column c is at 4*c + r.
    out = list(state)
    for r in range(1, 4):
        for c in range(4):
            out[4 * c + r] = state[4 * ((c + r) % 4) + r]
    return out


def _inv_shift_rows(state: list[int]) -> list[int]:
    out = list(state)
    for r in range(1, 4):
        for c in range(4):
            out[4 * ((c + r) % 4) + r] = state[4 * c + r]
    return out


def _mix_columns(state: list[int]) -> list[int]:
    out = []
    for c in range(4):
        a0, a1, a2, a3 = state[c * 4:c * 4 + 4]
        out.extend([
            _mul(a0, 2) ^ _mul(a1, 3) ^ a2 ^ a3,
            a0 ^ _mul(a1, 2) ^ _mul(a2, 3) ^ a3,
            a0 ^ a1 ^ _mul(a2, 2) ^ _mul(a3, 3),
            _mul(a0, 3) ^ a1 ^ a2 ^ _mul(a3, 2),
        ])
    return out


def _inv_mix_columns(state: list[int]) -> list[int]:
    out = []
    for c in range(4):
        a0, a1, a2, a3 = state[c * 4:c * 4 + 4]
        out.extend([
            _mul(a0, 14) ^ _mul(a1, 11) ^ _mul(a2, 13) ^ _mul(a3, 9),
            _mul(a0, 9) ^ _mul(a1, 14) ^ _mul(a2, 11) ^ _mul(a3, 13),
            _mul(a0, 13) ^ _mul(a1, 9) ^ _mul(a2, 14) ^ _mul(a3, 11),
            _mul(a0, 11) ^ _mul(a1, 13) ^ _mul(a2, 9) ^ _mul(a3, 14),
        ])
    return out


def encrypt_block_256(schedule: list[list[int]], block: bytes) -> bytes:
    state = _add_round_key(list(block), schedule[0])
    for rnd in range(1, 14):
        state = [SBOX[b] for b in state]
        state = _shift_rows(state)
        state = _mix_columns(state)
        state = _add_round_key(state, schedule[rnd])
    state = [SBOX[b] for b in state]
    state = _shift_rows(state)
    state = _add_round_key(state, schedule[14])
    return bytes(state)


def decrypt_block_256(schedule: list[list[int]], block: bytes) -> bytes:
    state = _add_round_key(list(block), schedule[14])
    for rnd in range(13, 0, -1):
        state = _inv_shift_rows(state)
        state = [INV_SBOX[b] for b in state]
        state = _add_round_key(state, schedule[rnd])
        state = _inv_mix_columns(state)
    state = _inv_shift_rows(state)
    state = [INV_SBOX[b] for b in state]
    state = _add_round_key(state, schedule[0])
    return bytes(state)


def decrypt_block_128(schedule: list[list[int]], block: bytes) -> bytes:
    state = _add_round_key(list(block), schedule[10])
    for rnd in range(9, 0, -1):
        state = _inv_shift_rows(state)
        state = [INV_SBOX[b] for b in state]
        state = _add_round_key(state, schedule[rnd])
        state = _inv_mix_columns(state)
    state = _inv_shift_rows(state)
    state = [INV_SBOX[b] for b in state]
    state = _add_round_key(state, schedule[0])
    return bytes(state)


def _fast_cipher(key: bytes):
    """Return ``(encrypt_block, decrypt_block)`` using ``cryptography``, or None."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception:  # pragma: no cover - depends on the host
        return None
    enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    dec = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return enc.update, dec.update


class Aes256:
    """AES-256, in pure Python or through the ``cryptography`` package."""

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AES-256 needs a 32-byte key")
        self._schedule = expand_key_256(key)
        fast = _fast_cipher(key)
        self._fast_enc = fast[0] if fast else None
        self._fast_dec = fast[1] if fast else None

    def encrypt(self, block: bytes) -> bytes:
        if len(block) != BLOCK:
            raise ValueError("AES blocks are 16 bytes")
        if self._fast_enc is not None:
            return self._fast_enc(block)
        return encrypt_block_256(self._schedule, block)

    def decrypt(self, block: bytes) -> bytes:
        if len(block) != BLOCK:
            raise ValueError("AES blocks are 16 bytes")
        if self._fast_dec is not None:
            return self._fast_dec(block)
        return decrypt_block_256(self._schedule, block)


class Aes128:
    """AES-128, in pure Python or through the ``cryptography`` package."""

    def __init__(self, key: bytes):
        if len(key) != 16:
            raise ValueError("AES-128 needs a 16-byte key")
        from aes import expand_key
        self._schedule = expand_key(key)
        fast = _fast_cipher(key)
        self._fast_enc = fast[0] if fast else None
        self._fast_dec = fast[1] if fast else None

    def encrypt(self, block: bytes) -> bytes:
        if len(block) != BLOCK:
            raise ValueError("AES blocks are 16 bytes")
        if self._fast_enc is not None:
            return self._fast_enc(block)
        from aes import encrypt_block
        return encrypt_block(self._schedule, block)

    def decrypt(self, block: bytes) -> bytes:
        if len(block) != BLOCK:
            raise ValueError("AES blocks are 16 bytes")
        if self._fast_dec is not None:
            return self._fast_dec(block)
        return decrypt_block_128(self._schedule, block)


def cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """Decrypt a buffer in AES-CBC mode.  The length must be a multiple of 16."""
    if len(iv) != BLOCK:
        raise ValueError("the IV is 16 bytes")
    if len(data) % BLOCK:
        raise ValueError("the CBC length must be a multiple of 16")
    if len(key) == 32:
        cipher = Aes256(key)
    elif len(key) == 16:
        cipher = Aes128(key)
    else:
        raise ValueError("AES needs a 16-byte or a 32-byte key")
    previous = iv
    out = bytearray()
    for i in range(0, len(data), BLOCK):
        block = data[i:i + BLOCK]
        plain = cipher.decrypt(block)
        out += bytes(a ^ b for a, b in zip(plain, previous))
        previous = block
    return bytes(out)


def cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """Encrypt a buffer in AES-CBC mode.  The length must be a multiple of 16."""
    if len(iv) != BLOCK:
        raise ValueError("the IV is 16 bytes")
    if len(data) % BLOCK:
        raise ValueError("the CBC length must be a multiple of 16")
    if len(key) == 32:
        cipher = Aes256(key)
    elif len(key) == 16:
        cipher = Aes128(key)
    else:
        raise ValueError("AES needs a 16-byte or a 32-byte key")
    previous = iv
    out = bytearray()
    for i in range(0, len(data), BLOCK):
        block = cipher.encrypt(bytes(a ^ b for a, b in zip(data[i:i + BLOCK], previous)))
        out += block
        previous = block
    return bytes(out)


def ecb_decrypt(key: bytes, data: bytes) -> bytes:
    """Decrypt a buffer in AES-ECB mode.  The length must be a multiple of 16."""
    if len(data) % BLOCK:
        raise ValueError("the ECB length must be a multiple of 16")
    if len(key) == 32:
        cipher = Aes256(key)
    elif len(key) == 16:
        cipher = Aes128(key)
    else:
        raise ValueError("AES needs a 16-byte or a 32-byte key")
    out = bytearray()
    for i in range(0, len(data), BLOCK):
        out += cipher.decrypt(data[i:i + BLOCK])
    return bytes(out)


def ctr_apply(key: bytes, iv: bytes, data: bytes) -> bytes:
    """XOR a buffer with the AES-CTR keystream.

    The counter is the 128-bit big-endian value of ``iv``; block ``n`` uses
    ``iv + n``.  The mode is its own inverse.
    """
    if len(iv) != BLOCK:
        raise ValueError("the IV is 16 bytes")
    counter = int.from_bytes(iv, "big")
    mask = (1 << 128) - 1
    fast = _fast_cipher(key)
    if fast is not None:
        encrypt = fast[0]
    else:
        cipher = Aes256(key) if len(key) == 32 else None
        if cipher is None:
            from aes import AES128
            cipher = AES128(key)
        encrypt = cipher.encrypt
    out = bytearray()
    for i in range(0, len(data), BLOCK):
        raw = ((counter + i // BLOCK) & mask).to_bytes(16, "big")
        keystream = encrypt(raw)
        chunk = data[i:i + BLOCK]
        out += bytes(a ^ b for a, b in zip(chunk, keystream))
    return bytes(out)

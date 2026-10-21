"""Tests of the cipher operations, against the FIPS-197 vectors."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from self_crypto import Aes128, Aes256, cbc_decrypt, cbc_encrypt, ctr_apply, ecb_decrypt  # noqa: E402

PLAINTEXT = bytes.fromhex("00112233445566778899aabbccddeeff")
AES128_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
AES128_CIPHER = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
AES256_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f"
                           "101112131415161718191a1b1c1d1e1f")
AES256_CIPHER = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")


class AesTest(unittest.TestCase):
    def test_aes128_matches_the_vector(self):
        self.assertEqual(Aes128(AES128_KEY).encrypt(PLAINTEXT), AES128_CIPHER)

    def test_aes256_matches_the_vector(self):
        self.assertEqual(Aes256(AES256_KEY).encrypt(PLAINTEXT), AES256_CIPHER)

    def test_aes128_decrypts(self):
        self.assertEqual(Aes128(AES128_KEY).decrypt(AES128_CIPHER), PLAINTEXT)

    def test_aes256_decrypts(self):
        self.assertEqual(Aes256(AES256_KEY).decrypt(AES256_CIPHER), PLAINTEXT)

    def test_cbc_round_trip(self):
        data = bytes(range(64))
        encrypted = cbc_encrypt(AES256_KEY, b"\x00" * 16, data)
        self.assertEqual(cbc_decrypt(AES256_KEY, b"\x00" * 16, encrypted), data)

    def test_cbc_with_aes128_round_trip(self):
        data = bytes(range(32))
        encrypted = cbc_encrypt(AES128_KEY, b"\x11" * 16, data)
        self.assertEqual(cbc_decrypt(AES128_KEY, b"\x11" * 16, encrypted), data)

    def test_ecb_decrypt_matches_the_vector(self):
        self.assertEqual(ecb_decrypt(AES128_KEY, AES128_CIPHER), PLAINTEXT)

    def test_ctr_is_its_own_inverse(self):
        data = bytes(range(64))
        once = ctr_apply(AES128_KEY, b"\x00" * 16, data)
        twice = ctr_apply(AES128_KEY, b"\x00" * 16, once)
        self.assertEqual(twice, data)

    def test_ctr_is_a_stream(self):
        # the keystream does not depend on the length of the data
        long = ctr_apply(AES128_KEY, b"\x00" * 16, bytes(64))
        short = ctr_apply(AES128_KEY, b"\x00" * 16, bytes(16))
        self.assertEqual(long[:16], short)

    def test_ctr_uses_a_big_endian_counter(self):
        # the second block uses the counter plus one
        data = ctr_apply(AES128_KEY, b"\x00" * 15 + b"\x00", bytes(32))
        second = ctr_apply(AES128_KEY, b"\x00" * 15 + b"\x01", bytes(16))
        self.assertEqual(data[16:], second)

    def test_a_wrong_length_is_refused(self):
        with self.assertRaises(ValueError):
            Aes128(b"\x00" * 15)
        with self.assertRaises(ValueError):
            Aes256(b"\x00" * 31)
        with self.assertRaises(ValueError):
            cbc_decrypt(AES128_KEY, b"\x00" * 16, bytes(17))


if __name__ == "__main__":
    unittest.main()

"""Password hashing tests."""

import unittest

from auth_password import hash_password, verify_password


class AuthPasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        stored = hash_password("secret123")
        self.assertTrue(stored.startswith("pbkdf2$"))
        self.assertTrue(verify_password("secret123", stored))
        self.assertFalse(verify_password("wrong", stored))

    def test_legacy_plaintext_fallback(self):
        self.assertTrue(verify_password("admin", "admin"))
        self.assertFalse(verify_password("wrong", "admin"))


if __name__ == "__main__":
    unittest.main()

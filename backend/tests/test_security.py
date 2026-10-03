from datetime import datetime, timezone
import unittest

from argon2 import PasswordHasher, Type
import jwt

from app.security import JWT_AUDIENCE, JWT_ISSUER, create_access_token, verify_password
from tests.helpers import test_settings


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "isolated-test-password"
        cls.password_hash = PasswordHasher(type=Type.ID).hash(cls.password)

    def test_verifies_existing_argon2id_hash_and_rejects_bad_credentials(self):
        self.assertTrue(self.password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(self.password, self.password_hash))
        self.assertFalse(verify_password("incorrect-test-password", self.password_hash))
        self.assertFalse(verify_password(self.password, "malformed-hash"))

    def test_jwt_contains_only_identification_and_expiry_claims(self):
        settings = test_settings()
        token = create_access_token(901, settings)
        claims = jwt.decode(
            token, settings.JWT_SECRET.get_secret_value(), algorithms=["HS256"],
            audience=JWT_AUDIENCE, issuer=JWT_ISSUER,
        )
        self.assertEqual(claims["sub"], "901")
        self.assertIn("exp", claims)
        self.assertGreater(claims["exp"], datetime.now(timezone.utc).timestamp())
        self.assertLessEqual(
            claims["exp"] - datetime.now(timezone.utc).timestamp(),
            settings.JWT_EXPIRE_MINUTES * 60,
        )
        for private_field in ("password", "password_hash", "document", "full_name"):
            self.assertNotIn(private_field, claims)
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(
                token, "different-isolated-test-secret-0123456789", algorithms=["HS256"],
                audience=JWT_AUDIENCE, issuer=JWT_ISSUER,
            )


if __name__ == "__main__":
    unittest.main()

"""Password hashing for student auth.

For demo simplicity we:
- use a standard passlib hash (pbkdf2_sha256)
- accept simple passwords without worrying about bcrypt-specific limits.

This keeps the login flow simple while we focus on learning features.
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _truncate(plain: str) -> str:
    return (plain or "")[:72]


def hash_password(plain: str) -> str:
    return pwd_context.hash(_truncate(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate(plain), hashed)


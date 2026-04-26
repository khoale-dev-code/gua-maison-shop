"""
app/utils/security.py
=====================
Hash & verify password dùng bcrypt.
Không lưu plain-text password vào DB.
"""

import bcrypt


def hash_password(plain: str) -> str:
    """Trả về chuỗi hash của password (bcrypt, cost=12)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """So sánh plain-text với hash, trả về True nếu khớp."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

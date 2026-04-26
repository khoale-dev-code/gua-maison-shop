"""
app/models/user_model.py
=========================
Model xử lý tất cả thao tác liên quan đến bảng `users` trên Supabase.
"""

from app.utils.supabase_client import get_supabase
from app.utils.security import hash_password, verify_password


class UserModel:

    @staticmethod
    def create(email: str, password: str, full_name: str, role: str = "customer") -> dict:
        """Tạo user mới – hash password trước khi lưu DB."""
        db = get_supabase()
        hashed = hash_password(password)
        result = db.table("users").insert({
            "email":         email,
            "password_hash": hashed,
            "full_name":     full_name,
            "role":          role,
        }).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    def get_by_email(email: str) -> dict | None:
        """Tìm user theo email, trả về None nếu không tìm thấy."""
        db = get_supabase()
        try:
            result = db.table("users").select("*").eq("email", email).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    def get_by_id(user_id: str) -> dict | None:
        db = get_supabase()
        try:
            result = db.table("users").select("*").eq("id", user_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    def authenticate(email: str, password: str) -> dict | None:
        """Xác thực email + password. Trả về user dict hoặc None."""
        user = UserModel.get_by_email(email)
        if not user:
            return None
        if verify_password(password, user.get("password_hash", "")):
            return user
        return None

    @staticmethod
    def email_exists(email: str) -> bool:
        """Kiểm tra email đã đăng ký chưa."""
        return UserModel.get_by_email(email) is not None

    @staticmethod
    def update_profile(user_id: str, data: dict) -> dict:
        db = get_supabase()
        result = db.table("users").update(data).eq("id", user_id).execute()
        return result.data[0] if result.data else {}

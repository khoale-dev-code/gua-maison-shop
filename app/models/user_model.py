"""
app/models/user_model.py
=========================
Model xử lý tất cả thao tác liên quan đến bảng `users` và phân quyền (RBAC) trên Supabase.
"""

import logging
from app.utils.supabase_client import get_supabase
from app.utils.security import hash_password, verify_password

logger = logging.getLogger(__name__)


class UserModel:

    @staticmethod
    def create(email: str, password: str, full_name: str, role_name: str="customer") -> dict:
        """
        Tạo user mới – hash password trước khi lưu DB.
        Đã nâng cấp: Tự động gán quyền thông qua bảng user_roles.
        """
        db = get_supabase()
        hashed = hash_password(password)
        
        try:
            # 1. Tạo tài khoản trong bảng users (Không còn truyền cột 'role' vào đây)
            user_result = db.table("users").insert({
                "email": email,
                "password_hash": hashed,
                "full_name": full_name,
            }).execute()
            
            user = user_result.data[0] if user_result.data else {}
            
            # 2. Xử lý gán quyền (RBAC) nếu tạo user thành công
            if user:
                # Tìm ID của quyền (ví dụ: 'customer' hoặc 'admin') trong bảng roles
                role_res = db.table("roles").select("id").eq("name", role_name).limit(1).execute()
                
                if role_res.data:
                    role_id = role_res.data[0]["id"]
                    # Gán quyền cho user
                    db.table("user_roles").insert({
                        "user_id": user["id"],
                        "role_id": role_id
                    }).execute()
                else:
                    logger.warning(f"Không tìm thấy quyền '{role_name}' trong bảng roles để gán cho user {email}.")
                    
            return user
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo user mới ({email}): {e}")
            return {}

    @staticmethod
    def get_by_email(email: str) -> dict | None:
        """Tìm user theo email, trả về None nếu không tìm thấy."""
        db = get_supabase()
        try:
            result = db.table("users").select("*").eq("email", email).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Lỗi get_by_email: {e}")
            return None

    @staticmethod
    def get_by_id(user_id: str) -> dict | None:
        """Tìm user theo ID."""
        db = get_supabase()
        try:
            result = db.table("users").select("*").eq("id", user_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Lỗi get_by_id: {e}")
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
        """Cập nhật thông tin profile của user."""
        db = get_supabase()
        try:
            result = db.table("users").update(data).eq("id", user_id).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Lỗi update_profile: {e}")
            return {}

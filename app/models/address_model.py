"""
app/models/address_model.py
Quản lý sổ địa chỉ của khách hàng và đồng bộ số điện thoại.
"""
import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class AddressModel:

    @staticmethod
    def get_user_addresses(user_id: str) -> list:
        """Lấy danh sách địa chỉ của user, đưa địa chỉ mặc định lên đầu."""
        db = get_supabase()
        try:
            result = db.table("user_addresses").select("*").eq("user_id", user_id).order("is_default", desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Lỗi get_user_addresses: {e}")
            return []

    @staticmethod
    def get_default_address(user_id: str) -> dict | None:
        """Lấy địa chỉ mặc định duy nhất của user."""
        db = get_supabase()
        try:
            result = db.table("user_addresses").select("*").eq("user_id", user_id).eq("is_default", True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Lỗi get_default_address: {e}")
            return None

    @staticmethod
    def add_address(user_id: str, data: dict) -> dict:
        """Thêm địa chỉ mới. Nếu là địa chỉ đầu tiên -> set làm mặc định và đồng bộ SĐT."""
        db = get_supabase()
        try:
            current_addresses = AddressModel.get_user_addresses(user_id)
            is_first = not current_addresses
            
            if is_first:
                data["is_default"] = True
                
            data["user_id"] = user_id
            result = db.table("user_addresses").insert(data).execute()
            
            if result.data:
                new_address = result.data[0]
                # Đồng bộ SĐT qua bảng users nếu đây là địa chỉ đầu tiên (mặc định)
                if is_first and new_address.get("phone"):
                    db.table("users").update({"phone": new_address["phone"]}).eq("id", user_id).execute()
                return new_address
            return {}
        except Exception as e:
            logger.error(f"Lỗi add_address: {e}")
            return {}

    @staticmethod
    def set_default(user_id: str, address_id: str) -> bool:
        """Đổi địa chỉ mặc định và đồng bộ SĐT mới qua bảng user."""
        db = get_supabase()
        try:
            # 1. Hủy mặc định của tất cả địa chỉ cũ
            db.table("user_addresses").update({"is_default": False}).eq("user_id", user_id).execute()
            
            # 2. Cài mặc định cho địa chỉ được chọn
            res = db.table("user_addresses").update({"is_default": True}).eq("id", address_id).execute()
            
            # 3. Đồng bộ SĐT
            if res.data:
                new_phone = res.data[0].get("phone")
                if new_phone:
                    db.table("users").update({"phone": new_phone}).eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi set_default: {e}")
            return False

    @staticmethod
    def update_address(user_id: str, address_id: str, data: dict) -> bool:
        """Cập nhật địa chỉ. Nếu đang là địa chỉ mặc định -> Đồng bộ lại SĐT."""
        db = get_supabase()
        try:
            # Đảm bảo chỉ cập nhật đúng địa chỉ của user này
            res = db.table("user_addresses").update(data).eq("user_id", user_id).eq("id", address_id).execute()
            
            if res.data:
                updated_address = res.data[0]
                # Nếu địa chỉ vừa sửa đang là mặc định, phải đồng bộ lại SĐT nhỡ khách vừa sửa SĐT
                if updated_address.get("is_default") and updated_address.get("phone"):
                    db.table("users").update({"phone": updated_address["phone"]}).eq("id", user_id).execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Lỗi update_address: {e}")
            return False

    @staticmethod
    def delete_address(user_id: str, address_id: str) -> bool:
        """Xóa địa chỉ."""
        db = get_supabase()
        try:
            db.table("user_addresses").delete().eq("user_id", user_id).eq("id", address_id).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi delete_address: {e}")
            return False

from app.utils.supabase_client import get_supabase


class AddressModel:

    @staticmethod
    def get_user_addresses(user_id: str) -> list:
        db = get_supabase()
        try:
            # Lấy danh sách, ưu tiên địa chỉ mặc định lên đầu
            result = db.table("user_addresses").select("*").eq("user_id", user_id).order("is_default", desc=True).execute()
            return result.data if result.data else []
        except Exception:
            return []

    @staticmethod
    def get_default_address(user_id: str) -> dict | None:
        db = get_supabase()
        try:
            result = db.table("user_addresses").select("*").eq("user_id", user_id).eq("is_default", True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    @staticmethod
    def add_address(user_id: str, data: dict) -> dict:
        db = get_supabase()
        # Kiểm tra xem user đã có địa chỉ nào chưa. Nếu chưa, ép cái này thành mặc định.
        current_addresses = AddressModel.get_user_addresses(user_id)
        if not current_addresses:
            data["is_default"] = True
            
        data["user_id"] = user_id
        result = db.table("user_addresses").insert(data).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    def set_default(user_id: str, address_id: str) -> bool:
        db = get_supabase()
        try:
            # B1: Hủy mặc định tất cả địa chỉ của user này
            db.table("user_addresses").update({"is_default": False}).eq("user_id", user_id).execute()
            # B2: Cài mặc định cho địa chỉ được chọn
            db.table("user_addresses").update({"is_default": True}).eq("id", address_id).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def delete_address(user_id: str, address_id: str) -> bool:
        db = get_supabase()
        try:
            db.table("user_addresses").delete().eq("user_id", user_id).eq("id", address_id).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def update_address(user_id: str, address_id: str, data: dict) -> bool:
        """Cập nhật thông tin địa chỉ đã có."""
        db = get_supabase()
        try:
            # Đảm bảo chỉ cập nhật địa chỉ thuộc về đúng user_id đó (bảo mật)
            result = db.table("user_addresses").update(data).eq("user_id", user_id).eq("id", address_id).execute()
            return True if result.data else False
        except Exception as e:
            return False

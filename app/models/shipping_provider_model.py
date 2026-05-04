"""
app/models/shipping_provider_model.py
CRUD cho bảng shipping_providers.
"""

import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class ShippingProviderModel:

    @staticmethod
    def _db():
        return get_supabase()

    @staticmethod
    def get_all(active_only: bool=False) -> list[dict]:
        """Lấy toàn bộ danh sách provider, sắp xếp theo sort_order ASC."""
        try:
            q = (
                ShippingProviderModel._db()
                .table("shipping_providers")
                .select("*")
                .order("sort_order", desc=False)  # ← FIX: phải có desc=False, thiếu direction gây lỗi một số version
            )
            if active_only:
                q = q.eq("is_active", True)
            return q.execute().data or []
        except Exception as e:
            logger.error(f"[ShippingProvider] get_all error: {e}")
            return []

    @staticmethod
    def get_by_id(provider_id: str) -> dict | None:
        """Trả None nếu không tìm thấy (thay vì {} để controller phân biệt được)."""
        try:
            res = (
                ShippingProviderModel._db()
                .table("shipping_providers")
                .select("*")
                .eq("id", provider_id)
                .maybe_single()  # ← FIX: dùng maybe_single() thay vì single()
                .execute()  #   single() raise exception khi không có row
            )  #   maybe_single() trả None — an toàn hơn
            return res.data  # None hoặc dict
        except Exception as e:
            logger.error(f"[ShippingProvider] get_by_id '{provider_id}' error: {e}")
            return None

    @staticmethod
    def create(data: dict) -> dict | None:
        """
        data cần có: id, name
        Optional: description, is_active, config (jsonb), icon, sort_order
        Trả None nếu thất bại (ID trùng hoặc lỗi DB).
        """
        try:
            res = (
                ShippingProviderModel._db()
                .table("shipping_providers")
                .insert(data)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"[ShippingProvider] create error: {e}")
            return None

    @staticmethod
    def update(provider_id: str, data: dict) -> dict | None:
        """Partial update. Trả None nếu không tìm thấy hoặc lỗi."""
        data.pop("id", None)  # Không cho phép đổi primary key
        if not data:
            return None
        try:
            res = (
                ShippingProviderModel._db()
                .table("shipping_providers")
                .update(data)
                .eq("id", provider_id)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"[ShippingProvider] update '{provider_id}' error: {e}")
            return None

    @staticmethod
    def delete(provider_id: str) -> bool:
        try:
            ShippingProviderModel._db().table("shipping_providers").delete().eq("id", provider_id).execute()
            return True
        except Exception as e:
            logger.error(f"[ShippingProvider] delete '{provider_id}' error: {e}")
            return False

    @staticmethod
    def toggle_active(provider_id: str) -> dict | None:
        """Đảo trạng thái is_active. Trả None nếu không tìm thấy."""
        current = ShippingProviderModel.get_by_id(provider_id)
        if not current:
            return None
        return ShippingProviderModel.update(provider_id, {"is_active": not current.get("is_active", False)})

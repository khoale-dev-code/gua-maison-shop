"""
app/services/shipping_service.py

Factory + Facade cho toàn bộ nghiệp vụ vận chuyển.

Luồng hoạt động:
  - PROVIDER_REGISTRY: map id → Class (code-level, bất biến)
  - shipping_providers (DB): quản lý is_active, config (API key/token), metadata UI

Thêm provider mới:
  1. Tạo class trong app/services/shipping/ kế thừa BaseShippingProvider
  2. Đăng ký vào PROVIDER_REGISTRY
  3. Thêm bản ghi vào bảng shipping_providers qua trang Admin
"""

import logging
from .shipping.mock      import MockShippingProvider
from .shipping.ghn       import GHNShippingProvider
from .shipping.self_ship import SelfShipProvider

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
#  REGISTRY: id → Class  (chỉ sửa khi thêm/xoá provider ở code)
# ══════════════════════════════════════════════════════════════════
PROVIDER_REGISTRY: dict = {
    "mock": MockShippingProvider,
    "ghn": GHNShippingProvider,
    "self_ship": SelfShipProvider,
    # "ghtk": GHTKShippingProvider,
}

_FALLBACK = "mock"


class ShippingService:

    @staticmethod
    def get_provider(provider_name: str):
        """
        Factory Method: Khởi tạo provider theo tên.
        Nếu provider có config trong DB → inject vào instance.
        Fallback về Mock nếu không tìm thấy trong registry.
        """
        provider_cls = PROVIDER_REGISTRY.get(provider_name)
        if provider_cls is None:
            logger.warning(
                f"[ShippingService] Provider '{provider_name}' không có trong registry. "
                f"Fallback về '{_FALLBACK}'."
            )
            provider_cls = PROVIDER_REGISTRY[_FALLBACK]

        instance = provider_cls()

        # Inject config từ DB (nếu có) để override .env
        # VD: GHN token/shop_id lưu trong shipping_providers.config (jsonb)
        try:
            from app.models.shipping_provider_model import ShippingProviderModel
            db_row = ShippingProviderModel.get_by_id(provider_name)
            if db_row and db_row.get("config"):
                ShippingService._inject_config(instance, db_row["config"])
        except Exception as e:
            logger.warning(f"[ShippingService] Không inject được config DB cho '{provider_name}': {e}")

        return instance

    @staticmethod
    def _inject_config(instance, config: dict):
        """
        Ghi đè các attribute của provider instance bằng config từ DB.
        Chỉ ghi đè những key đã có sẵn trên instance (an toàn).

        VD config jsonb trong DB cho GHN:
          {"token": "abc123", "shop_id": "12345", "base_url": "https://..."}
        """
        for key, value in config.items():
            if hasattr(instance, key) and value:
                setattr(instance, key, value)

    @staticmethod
    def list_providers(active_only: bool=False) -> list[dict]:
        """
        Trả về danh sách provider từ DB (shipping_providers table).
        Ưu tiên dữ liệu DB, fallback về PROVIDER_REGISTRY nếu DB lỗi.

        active_only=True: chỉ lấy hãng đang bật (dùng cho modal tạo vận đơn).
        """
        try:
            from app.models.shipping_provider_model import ShippingProviderModel
            rows = ShippingProviderModel.get_all(active_only=active_only)
            if rows:
                # Chỉ trả về những provider có class trong registry (đã code xong)
                return [
                    {
                        "id": r["id"],
                        "label": r["name"],
                        "name": r["name"],
                        "icon": r.get("icon", "📦"),
                        "description": r.get("description", ""),
                        "is_active": r.get("is_active", False),
                        "sort_order": r.get("sort_order", 0),
                    }
                    for r in rows
                    if r["id"] in PROVIDER_REGISTRY
                ]
        except Exception as e:
            logger.error(f"[ShippingService] list_providers từ DB lỗi: {e}")

        # ── Fallback: đọc thẳng từ PROVIDER_REGISTRY ──
        logger.warning("[ShippingService] Fallback list_providers về PROVIDER_REGISTRY.")
        _labels = {
            "mock": {"label": "MOCK (Test nội bộ)", "icon": "🧪", "description": "Môi trường test an toàn"},
            "ghn": {"label": "Giao Hàng Nhanh (GHN)", "icon": "🚀", "description": "API v2 — Toàn quốc"},
            "ghtk": {"label": "Giao Hàng Tiết Kiệm (GHTK)", "icon": "💰", "description": "Tiết kiệm chi phí"},
            "self_ship": {"label": "Tự giao hàng", "icon": "🏍️", "description": "Nhân viên shop giao trực tiếp"},
        }
        return [
            {"id": pid, "is_active": True, "sort_order": 0, **_labels.get(pid, {"label": pid, "icon": "📦", "description": ""})}
            for pid in PROVIDER_REGISTRY
        ]

    @staticmethod
    def calculate_fee(provider_name: str, payload: dict) -> dict:
        return ShippingService.get_provider(provider_name).calculate_fee(payload)

    @staticmethod
    def create_order(provider_name: str, payload: dict, shipment_db_id: str=None) -> dict:
        """
        Tạo vận đơn với hãng vận chuyển.
        Nếu thành công + có shipment_db_id → tự lưu tracking_code vào DB.
        """
        provider = ShippingService.get_provider(provider_name)
        result = provider.create_order(payload)

        if result.get("success") and shipment_db_id:
            try:
                from app.models.shipment_model import ShipmentModel

                ShipmentModel.update_provider_info(
                    shipment_id=shipment_db_id,
                    provider=provider_name,
                    tracking_code=result.get("tracking_code", ""),
                    raw_response=result.get("raw_response", {}),
                )

                desc = (
                    f"Vận đơn nội bộ đã tạo. Mã: {result.get('tracking_code', '')}. "
                    f"Nhân viên shop sẽ giao trực tiếp."
                    if provider_name == "self_ship"
                    else
                    f"Vận đơn đã tạo qua {provider_name.upper()}. "
                    f"Mã: {result.get('tracking_code', '')}"
                )

                ShipmentModel.log_event(
                    shipment_id=shipment_db_id,
                    status="shipped",
                    description=desc,
                )

            except Exception as e:
                logger.error(f"[ShippingService] Lỗi lưu tracking_code vào DB: {e}")

        return result

    @staticmethod
    def get_provider_display(provider_id: str) -> dict:
        """
        Lấy thông tin hiển thị (tên, icon) của 1 provider theo id.
        Dùng trong Order Detail để render badge hãng vận chuyển.
        """
        try:
            from app.models.shipping_provider_model import ShippingProviderModel
            row = ShippingProviderModel.get_by_id(provider_id)
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "icon": row.get("icon", "📦"),
                }
        except Exception:
            pass
        # Fallback nhẹ
        return {"id": provider_id, "name": provider_id.upper(), "icon": "📦"}

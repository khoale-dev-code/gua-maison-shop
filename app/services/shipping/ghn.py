"""
app/services/shipping/ghn.py

Provider GHN (Giao Hàng Nhanh) — Môi trường DEV/PROD.

Thứ tự ưu tiên config:
  1. shipping_providers.config (jsonb) trong DB   ← Admin nhập qua UI
  2. Flask config / .env                          ← fallback
  3. Chuỗi rỗng                                   ← chưa cấu hình

Để chuyển sang Production:
  - Đổi base_url trong DB config hoặc GHN_BASE_URL trong .env
  - Hoặc sửa thẳng default bên dưới
"""

import logging
import requests
from flask import current_app
from .base import BaseShippingProvider

logger = logging.getLogger(__name__)


class GHNShippingProvider(BaseShippingProvider):

    def __init__(self):
        # Đọc từ Flask config (.env) — ShippingService._inject_config()
        # sẽ override bằng giá trị từ DB nếu có
        try:
            self.token = current_app.config.get("GHN_TOKEN", "")
            self.shop_id = current_app.config.get("GHN_SHOP_ID", "")
            self.base_url = current_app.config.get(
                "GHN_BASE_URL",
                "https://dev-online-gateway.ghn.vn/shiip/public-api/v2"
            )
        except RuntimeError:
            # Ngoài application context (unit test)
            self.token = ""
            self.shop_id = ""
            self.base_url = "https://dev-online-gateway.ghn.vn/shiip/public-api/v2"

        self.timeout = 10

    @property
    def _headers(self) -> dict:
        return {
            "Token": self.token,
            "ShopId": str(self.shop_id),
            "Content-Type": "application/json",
        }

    def _is_configured(self) -> bool:
        return bool(
            self.token and self.shop_id
            and self.token   not in ("", "your_ghn_token")
            and self.shop_id not in ("", "your_shop_id")
        )

    # ─────────────────────────────────────────────
    #  TÍNH PHÍ VẬN CHUYỂN
    # ─────────────────────────────────────────────

    def calculate_fee(self, payload: dict) -> dict:
        if not self._is_configured():
            return {
                "success": False, "fee": 0,
                "raw_response": {
                    "error": "GHN chưa được cấu hình. Vui lòng nhập Token và Shop ID trong trang Đơn vị vận chuyển.",
                    "code": 401,
                },
            }
        try:
            ghn_payload = {
                "service_type_id": payload.get("service_type_id", 2),
                "to_district_id": payload.get("to_district_id"),
                "to_ward_code": payload.get("to_ward_code", ""),
                "weight": payload.get("weight", 500),
                "insurance_value": payload.get("cod_amount", 0),
            }
            res = requests.post(f"{self.base_url}/shipping-order/fee", json=ghn_payload, headers=self._headers, timeout=self.timeout)
            data = res.json()

            if res.status_code == 200 and data.get("code") == 200:
                return {
                    "success": True,
                    "fee": data["data"]["total"],
                    "estimated_days": data["data"].get("expected_delivery_time", ""),
                    "raw_response": data,
                }
            return {"success": False, "fee": 0, "raw_response": data}

        except requests.exceptions.Timeout:
            logger.error("[GHN] calculate_fee timeout")
            return {"success": False, "fee": 0, "raw_response": {"error": "API GHN timeout"}}
        except Exception as e:
            logger.error(f"[GHN] calculate_fee lỗi: {e}")
            return {"success": False, "fee": 0, "raw_response": {"error": str(e)}}

    # ─────────────────────────────────────────────
    #  TẠO VẬN ĐƠN
    # ─────────────────────────────────────────────

    def create_order(self, order_data: dict) -> dict:
        if not self._is_configured():
            return {
                "success": False, "tracking_code": "",
                "raw_response": {
                    "error": "GHN chưa được cấu hình. Vui lòng nhập Token và Shop ID trong trang Đơn vị vận chuyển.",
                    "code": 401,
                },
            }
        try:
            ghn_payload = {
                "payment_type_id": 2,
                "required_note": "CHOXEMHANGKHONGTHU",
                "to_name": order_data.get("to_name", ""),
                "to_phone": order_data.get("to_phone", ""),
                "to_address": order_data.get("to_address", ""),
                "to_district_id": order_data.get("to_district_id"),
                "to_ward_code": order_data.get("to_ward_code", ""),
                "weight": order_data.get("weight", 500),
                "cod_amount": int(order_data.get("cod_amount", 0)),
                "service_type_id": 2,
                "items": order_data.get("items", [{
                    "name": "Hàng thời trang",
                    "quantity": 1,
                    "weight": order_data.get("weight", 500),
                }]),
            }
            res = requests.post(f"{self.base_url}/shipping-order/create", json=ghn_payload, headers=self._headers, timeout=self.timeout)
            data = res.json()

            if res.status_code == 200 and data.get("code") == 200:
                return {"success": True, "tracking_code": data["data"]["order_code"], "raw_response": data}
            return {"success": False, "tracking_code": "", "raw_response": data}

        except requests.exceptions.Timeout:
            logger.error("[GHN] create_order timeout")
            return {"success": False, "tracking_code": "", "raw_response": {"error": "API GHN timeout"}}
        except Exception as e:
            logger.error(f"[GHN] create_order lỗi: {e}")
            return {"success": False, "tracking_code": "", "raw_response": {"error": str(e)}}

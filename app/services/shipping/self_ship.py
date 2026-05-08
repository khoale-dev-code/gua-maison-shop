"""
app/services/shipping/self_ship.py

Provider "Tự giao hàng" — Giao trực tiếp từ shop, không qua bên thứ 3.

Kịch bản áp dụng:
  - Shop có xe giao hàng riêng (moto/ô tô)
  - Giao hàng nội thành cho khách VIP
  - Giao hàng thử khi chưa ký hợp đồng với hãng nào
  - Test luồng mà không muốn dùng Mock

Khác với Mock:
  - Mock  → dùng để TEST CODE (dữ liệu giả, không có nghĩa vụ thực)
  - Self  → dùng để VẬN HÀNH THẬT (nhân viên nhà giao, tracking bằng tay)

Tracking code: Tự sinh dạng GUA-YYYYMMDD-XXXXXX
Cập nhật trạng thái: Admin cập nhật bằng tay qua trang Order Detail,
                     hoặc tích hợp QR scan sau này.
"""

import random
import string
from datetime import datetime
from flask import current_app
from .base import BaseShippingProvider


def _gen_tracking_code() -> str:
    """Sinh mã vận đơn nội bộ GUA-YYYYMMDD-XXXXXX"""
    date_str = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"GUA-{date_str}-{suffix}"


class SelfShipProvider(BaseShippingProvider):
    """
    Giao hàng nội bộ — Nhân viên shop trực tiếp giao.
    Không gọi API ngoài. Luôn thành công ngay lập tức.
    """

    def __init__(self):
        # Phí giao nội bộ cấu hình trong .env, mặc định là 0
        try:
            self.internal_fee = int(current_app.config.get("SELF_SHIP_FEE", 0))
            self.shop_name = current_app.config.get("SHOP_NAME", "GUA Maison")
        except RuntimeError:
            self.internal_fee = 0
            self.shop_name = "GUA Maison"

    def calculate_fee(self, payload: dict) -> dict:
        """
        Phí giao nội bộ — có thể cấu hình qua SELF_SHIP_FEE trong .env.
        Mặc định miễn phí (0đ) — đặc quyền giao nội bộ.
        """
        return {
            "success": True,
            "fee": self.internal_fee,
            "estimated_days": 1,
            "raw_response": {
                "message": f"Giao hàng nội bộ bởi {self.shop_name}",
                "fee": self.internal_fee,
                "note": "Không qua đơn vị vận chuyển thứ 3. Nhân viên shop trực tiếp giao."
            }
        }

    def create_order(self, order_data: dict) -> dict:
        """
        'Tạo vận đơn' nội bộ — Sinh mã GUA-YYYYMMDD-XXXXXX.
        Không gọi API bên ngoài. Tracking bằng cách admin tự cập nhật
        trạng thái trên trang Order Detail.
        """
        tracking_code = _gen_tracking_code()

        return {
            "success": True,
            "tracking_code": tracking_code,
            "raw_response": {
                "message": f"Vận đơn nội bộ đã tạo bởi {self.shop_name}",
                "tracking_code": tracking_code,
                "type": "self_ship",
                "instructions": (
                    "Nhân viên giao hàng cần cập nhật trạng thái thủ công "
                    "trên trang quản lý đơn hàng khi: (1) Đã lấy hàng, "
                    "(2) Đang giao, (3) Giao thành công / Thất bại."
                ),
                "recipient": {
                    "name": order_data.get("to_name", ""),
                    "phone": order_data.get("to_phone", ""),
                    "address": order_data.get("to_address", ""),
                }
            }
        }

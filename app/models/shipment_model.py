"""
app/models/shipment_model.py
Quản lý dữ liệu Vận chuyển (Shipments) và Lịch sử hành trình (Shipment Events).
"""

import logging
from datetime import datetime, timezone
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class ShipmentModel:

    @staticmethod
    def _db():
        """Helper lấy kết nối Supabase"""
        return get_supabase()

    @staticmethod
    def create_shipment(data: dict) -> dict:
        """
        Tạo Shipment mới, lưu snapshot dữ liệu người nhận.
        Sau khi tạo thành công sẽ tự động ghi 1 log sự kiện khởi tạo.
        """
        try:
            db = ShipmentModel._db()
            res = db.table("shipments").insert(data).execute()
            
            if res.data:
                shipment = res.data[0]
                
                # Lấy trạng thái từ data truyền vào (mặc định pending_pickup)
                status = shipment.get("status", "pending_pickup")
                
                # Tự động ghi event khởi tạo đầu tiên
                ShipmentModel.log_event(
                    shipment_id=shipment["id"],
                    status=status,
                    description="Khởi tạo dữ liệu vận chuyển, chờ bàn giao cho đối tác."
                )
                return shipment
            return {}
        except Exception as e:
            logger.error(f"Lỗi create_shipment: {e}")
            return {}

    @staticmethod
    def log_event(shipment_id: str, status: str, description: str, location: str="", raw_data: dict=None) -> bool:
        """
        Ghi lại 1 mốc thời gian hành trình (Event Sourcing).
        Đồng thời cập nhật lại trạng thái (status) mới nhất cho Shipment.
        """
        if raw_data is None:
            raw_data = {}
            
        try:
            db = ShipmentModel._db()
            
            # 1. Thêm event lịch sử mới vào bảng shipment_events
            db.table("shipment_events").insert({
                "shipment_id": shipment_id,
                "status": status,
                "description": description,
                "location": location,
                "raw_data": raw_data
            }).execute()

            # 2. Cập nhật status hiện tại của bảng shipments
            update_data = {"status": status}
            
            # Nếu trạng thái là đang giao hoặc đã giao -> Cập nhật thời gian thực tế để làm báo cáo
            now_iso = datetime.now(timezone.utc).isoformat()
            if status == "shipping":
                update_data["shipped_at"] = now_iso
            elif status == "delivered":
                update_data["delivered_at"] = now_iso

            db.table("shipments").update(update_data).eq("id", shipment_id).execute()
            return True
            
        except Exception as e:
            logger.error(f"Lỗi log_shipment_event cho ID {shipment_id}: {e}")
            return False

    @staticmethod
    def get_by_order_id(order_id: str) -> dict:
        """
        Lấy thông tin vận chuyển của một đơn hàng, 
        kèm theo toàn bộ lịch sử hành trình (shipment_events).
        """
        try:
            db = ShipmentModel._db()
            
            # Lấy shipment mới nhất của Order (Đề phòng có shipment bị retry)
            res = (
                db.table("shipments")
                .select("*, shipment_events(*)")
                .eq("order_id", order_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            
            if not res.data:
                return {}
                
            shipment = res.data[0]
            
            # Đảm bảo mảng timeline luôn được sắp xếp: Mới nhất nằm trên cùng
            if "shipment_events" in shipment and isinstance(shipment["shipment_events"], list):
                shipment["shipment_events"].sort(
                    key=lambda x: x.get("created_at", ""),
                    reverse=True
                )
                
            return shipment
        except Exception as e:
            logger.error(f"Lỗi get_by_order_id cho Order {order_id}: {e}")
            return {}

    @staticmethod
    def update_provider_info(shipment_id: str, provider: str, tracking_code: str, raw_response: dict=None) -> bool:
        """Cập nhật mã vận đơn và hãng vận chuyển sau khi bắn API thành công"""
        try:
            data = {
                "provider": provider,
                "tracking_code": tracking_code
            }
            if raw_response:
                data["raw_response"] = raw_response
                
            res = ShipmentModel._db().table("shipments").update(data).eq("id", shipment_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"Lỗi update_provider_info: {e}")
            return False

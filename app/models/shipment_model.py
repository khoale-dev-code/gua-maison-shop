"""
app/models/shipment_model.py
Quản lý dữ liệu Vận chuyển (Shipments), Đối soát tài chính, Lịch sử hành trình và Webhook.
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

    # ═══════════════════════════════════════════════════════════════
    #  QUẢN LÝ VẬN ĐƠN (SHIPMENTS)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def create_shipment(data: dict) -> dict:
        """
        Tạo Shipment mới, lưu snapshot dữ liệu người nhận, phí ship, kích thước.
        Sau khi tạo thành công sẽ tự động ghi 1 log sự kiện khởi tạo.
        """
        try:
            db = ShipmentModel._db()
            res = db.table("shipments").insert(data).execute()
            
            if res.data:
                shipment = res.data[0]
                
                # Lấy trạng thái từ data truyền vào (mặc định pending)
                status = shipment.get("status", "pending")
                
                # Tự động ghi event khởi tạo đầu tiên
                ShipmentModel.log_event(
                    shipment_id=shipment["id"],
                    status=status,
                    description="Khởi tạo dữ liệu vận chuyển, chờ xử lý."
                )
                return shipment
            return {}
        except Exception as e:
            logger.error(f"Lỗi create_shipment: {e}")
            return {}

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
    def update_shipment_details(shipment_id: str, update_data: dict) -> bool:
        """
        Cập nhật thông tin vận đơn (Mã tracking, Phí thực tế, SLA, v.v.)
        Thay thế cho hàm update_provider_info cũ để linh hoạt hơn.
        """
        try:
            res = ShipmentModel._db().table("shipments").update(update_data).eq("id", shipment_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"Lỗi update_shipment_details ID {shipment_id}: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  QUẢN LÝ HÀNH TRÌNH (EVENTS & SLA)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def log_event(shipment_id: str, status: str, description: str, location: str="", raw_data: dict=None) -> bool:
        """
        Ghi lại 1 mốc thời gian hành trình (Event Sourcing).
        Đồng thời cập nhật lại trạng thái (status) và SLA mới nhất cho Shipment.
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
            
            # Xử lý cập nhật Thời gian thực tế để tính toán SLA & Báo cáo
            now_iso = datetime.now(timezone.utc).isoformat()
            if status in ["shipped", "in_transit", "out_for_delivery"]:
                # Chỉ set shipped_at ở lần đầu tiên bắt đầu giao
                shipment_info = db.table("shipments").select("shipped_at").eq("id", shipment_id).single().execute().data
                if shipment_info and not shipment_info.get("shipped_at"):
                    update_data["shipped_at"] = now_iso
            elif status == "delivered":
                update_data["delivered_at"] = now_iso

            db.table("shipments").update(update_data).eq("id", shipment_id).execute()
            return True
            
        except Exception as e:
            logger.error(f"Lỗi log_event cho ID {shipment_id}: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  WEBHOOK & CARRIER MAPPING (TÍNH NĂNG MỚI)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_internal_status(provider: str, carrier_status: str, default_status: str="in_transit") -> str:
        """
        Dịch trạng thái của Hãng (Ví dụ GHN: 'ready_to_pick') 
        sang chuẩn trạng thái nội bộ của GUA (Ví dụ: 'waiting_pickup').
        """
        try:
            db = ShipmentModel._db()
            res = (
                db.table("carrier_status_mapping")
                .select("internal_status")
                .eq("provider", provider)
                .eq("carrier_status", carrier_status)
                .limit(1)
                .execute()
            )
            
            if res.data:
                return res.data[0]["internal_status"]
                
            # Nếu hãng trả về một mã mới chưa có trong DB, cảnh báo và dùng default
            logger.warning(f"[Mapping Missing] Hãng {provider} gửi trạng thái lạ: '{carrier_status}'. Dùng mặc định: '{default_status}'")
            return default_status
        except Exception as e:
            logger.error(f"Lỗi get_internal_status: {e}")
            return default_status

    @staticmethod
    def log_webhook(provider: str, event_type: str, payload: dict, status_code: int=200, error_message: str=None) -> bool:
        """
        Lưu vết (Log) toàn bộ dữ liệu Webhook gửi đến từ các hãng.
        Phục vụ cho việc debug, xử lý sự cố, tranh chấp bồi thường.
        """
        try:
            db = ShipmentModel._db()
            db.table("webhook_logs").insert({
                "provider": provider,
                "event_type": event_type,
                "payload": payload,
                "status_code": status_code,
                "error_message": error_message
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi log_webhook: {e}")
            return False

"""
app/services/audit_service.py
Dịch vụ ghi log tự động các thao tác của Admin/Nhân viên trên hệ thống.
"""
import logging
from flask import request, session
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class AuditService:

    @staticmethod
    def log(action: str, table_name: str, record_id: str, old_values: dict=None, new_values: dict=None):
        """Ghi log hành động vào bảng audit_logs"""
        try:
            user_id = session.get("user_id")
            tenant_id = session.get("tenant_id")  # Trống cũng không sao nếu chưa dùng multi-tenant
            ip_address = request.remote_addr if request else "Unknown"
            user_agent = request.user_agent.string if request else "Unknown"

            db = get_supabase()
            db.table("audit_logs").insert({
                "tenant_id": tenant_id,
                "user_id": user_id,
                "action": action.upper(),
                "table_name": table_name,
                "record_id": str(record_id),
                "old_values": old_values or {},
                "new_values": new_values or {},
                "ip_address": ip_address,
                "user_agent": user_agent
            }).execute()
        except Exception as e:
            logger.error(f"[Audit Log Error] Không thể ghi log {action} trên {table_name}: {e}")

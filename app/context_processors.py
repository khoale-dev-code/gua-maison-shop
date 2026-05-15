"""
app/context_processors.py
Inject biến toàn cục vào mọi template.

Thay đổi: pending_returns giờ query cho cả 'admin' lẫn 'staff'
          (trước đây chỉ query khi role == 'admin' nên staff không thấy badge).
"""

import logging
from flask import session
from app.utils.supabase_client import get_supabase
from app.models.cart_model import CartModel
from app.models.category_model import CategoryModel
from app.models.setting_model import SettingModel

logger = logging.getLogger(__name__)


def inject_globals() -> dict:
    cart_count = 0
    categories = []
    pending_returns = 0
    system_settings = {}

    user_id = session.get("user_id")
    role = session.get("role")

    # System settings
    try:
        system_settings = SettingModel.get_settings()
    except Exception:
        logger.warning("context_processor: Lỗi khi lấy system_settings.")

    # Thông báo chưa đọc
    unread_notification_count = 0
    if user_id:
        try:
            cart_count = CartModel.get_count(user_id)
        except Exception:
            pass
        try:
            from app.models.notification_model import NotificationModel
            unread_notification_count = NotificationModel.get_unread_count(user_id)
        except Exception:
            pass

    # Categories
    try:
        categories = CategoryModel.get_all()
    except Exception:
        pass

    # pending_returns: hiện cho cả admin và staff vào trang /admin
    # (staff cần thấy badge đổi/trả nếu họ có quyền xử lý)
    if role in ("admin", "staff"):
        try:
            r = (
                get_supabase()
                .table("return_requests")
                .select("id", count="exact")
                .eq("status", "pending")
                .execute()
            )
            pending_returns = r.count or 0
        except Exception as e:
            logger.warning(f"context_processor: không lấy được pending_returns — {e}")

    return {
        "current_user": {
            "id": user_id,
            "email": session.get("email"),
            "full_name": session.get("full_name"),
            "role": role,
            # admin_role_slug hữu ích để template kiểm tra quyền cụ thể
            "admin_role_slug": session.get("admin_role_slug"),
        },
        "cart_count": cart_count,
        "global_categories": categories,
        "pending_returns": pending_returns,
        "system_settings": system_settings,
        "unread_notification_count": unread_notification_count,
    }

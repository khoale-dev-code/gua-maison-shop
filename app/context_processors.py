"""
app/context_processors.py
Inject biến toàn cục vào mọi template — không cần truyền tay từng route.

Đăng ký trong app/__init__.py:
    from app.context_processors import inject_admin_globals
    app.context_processor(inject_admin_globals)
"""

import logging
from flask import session
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def inject_admin_globals():
    """
    Inject `pending_returns` (số yêu cầu đổi/trả đang chờ duyệt) vào
    mọi template.

    - Chỉ query DB khi người dùng đang đăng nhập với role admin.
    - Trả về 0 nếu không phải admin hoặc có lỗi — không bao giờ raise.
    - Kết quả được Flask cache trong request context (gọi 1 lần/request).
    """
    pending_returns = 0

    if session.get("role") == "admin":
        try:
            db = get_supabase()
            r = (
                db.table("return_requests")
                .select("id", count="exact")
                .eq("status", "pending")
                .execute()
            )
            pending_returns = r.count or 0
        except Exception as e:
            logger.warning(f"context_processor: không lấy được pending_returns — {e}")

    return {"pending_returns": pending_returns}

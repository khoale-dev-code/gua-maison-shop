"""
app/middleware/auth_required.py
"""

import logging
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from typing import Callable, Any
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def _is_admin(user_id: str) -> bool:
    """
    Kiểm tra quyền admin bằng 2 bước riêng biệt.
    Tránh lỗi Supabase client khi join bảng có tenant_id nullable.
    """
    try:
        db = get_supabase()

        # Bước 1: Lấy role_id của user
        ur_res = db.table("user_roles").select("role_id").eq("user_id", user_id).execute()
        if not ur_res.data:
            return False

        role_ids = [row["role_id"] for row in ur_res.data]

        # Bước 2: Kiểm tra trong bảng roles có tên 'admin' không
        roles_res = (
            db.table("roles")
            .select("name")
            .in_("id", role_ids)
            .execute()
        )
        if not roles_res.data:
            return False

        return any(row["name"] == "admin" for row in roles_res.data)

    except Exception as e:
        logger.error(f"[RBAC Critical] Lỗi xác thực quyền cho user_id={user_id}: {e}")
        return False


def login_required(f: Callable) -> Callable:

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def admin_required(f: Callable) -> Callable:

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        user_id = session.get("user_id")

        if not user_id:
            flash("Vui lòng đăng nhập tài khoản quản trị.", "warning")
            return redirect(url_for("auth.login", next=request.url))

        # Ưu tiên dùng role trong session (đã được verify lúc login)
        # Nhưng vẫn double-check với DB để chống giả mạo session
        session_role = session.get("role")
        if session_role == "admin":
            # Session nói là admin → tin tưởng, không query DB thêm (hiệu năng)
            return f(*args, **kwargs)

        # Session không phải admin → query DB để chắc chắn
        if _is_admin(user_id):
            # Cập nhật lại session nếu role đã được thay đổi trong DB
            session["role"] = "admin"
            return f(*args, **kwargs)

        flash("Bạn không có quyền truy cập khu vực này.", "danger")
        if request.method == "POST" or request.is_json:
            return abort(403)
        return redirect(url_for("products.index"))

    return decorated

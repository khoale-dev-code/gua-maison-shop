"""
app/middleware/auth_required.py
================================
Middleware xác thực & phân quyền dựa trên schema thực tế:
  - users.role      : 'admin' (super admin) | 'staff' | 'customer'
  - users.admin_role_slug : FK -> admin_roles.slug  (chỉ áp dụng cho staff)
  - admin_roles.permissions (JSONB): danh sách permission codes

  KHÔNG dùng bảng roles / user_roles / permissions / role_permissions
  vì các bảng đó không tồn tại trong schema hiện tại.
"""

import logging
from functools import wraps
from typing import Callable, Any

from flask import session, redirect, url_for, flash, request, abort, g
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────


def _get_user_record(user_id: str) -> dict | None:
    """
    Lấy thông tin user từ DB (có cache trong g để tránh query nhiều lần / request).
    Trả về dict user hoặc None.
    """
    if hasattr(g, "_auth_user"):
        return g._auth_user

    try:
        db = get_supabase()
        res = db.table("users") \
                .select("id, role, is_suspended, admin_role_slug") \
                .eq("id", user_id) \
                .limit(1) \
                .execute()
        user = res.data[0] if res.data else None
        g._auth_user = user
        return user
    except Exception as e:
        logger.error(f"[auth_required] Lỗi lấy user_id={user_id}: {e}")
        return None


def _get_admin_role_permissions(slug: str) -> list:
    """
    Lấy danh sách quyền của một admin_role từ bảng admin_roles.
    permissions là JSONB – có thể là list[str] hoặc dict.
    Cache trong g._admin_role_perms để tránh query lặp.
    """
    cache = getattr(g, "_admin_role_perms", {})
    if slug in cache:
        return cache[slug]

    try:
        db = get_supabase()
        res = db.table("admin_roles") \
                .select("permissions") \
                .eq("slug", slug) \
                .limit(1) \
                .execute()
        if res.data:
            raw = res.data[0].get("permissions") or []
            # Hỗ trợ 2 format: ["orders.view", ...] hoặc {"orders.view": true, ...}
            if isinstance(raw, list):
                perms = raw
            elif isinstance(raw, dict):
                perms = [k for k, v in raw.items() if v]
            else:
                perms = []
        else:
            perms = []
    except Exception as e:
        logger.error(f"[auth_required] Lỗi lấy quyền admin_role slug={slug}: {e}")
        perms = []

    if not hasattr(g, "_admin_role_perms"):
        g._admin_role_perms = {}
    g._admin_role_perms[slug] = perms
    return perms


def _is_super_admin(user: dict) -> bool:
    """Super admin: users.role == 'admin'"""
    return user.get("role") == "admin"


def _is_staff(user: dict) -> bool:
    """Staff (nhân viên hạn chế): users.role == 'staff'"""
    return user.get("role") == "staff"


def _can_access_admin(user: dict) -> bool:
    """Có thể vào khu vực /admin không?"""
    return _is_super_admin(user) or _is_staff(user)


def _has_permission(user: dict, permission_code: str) -> bool:
    """
    Kiểm tra quyền cụ thể:
    - Super admin: luôn True (toàn quyền)
    - Staff: kiểm tra permission_code trong admin_roles.permissions
    - Còn lại: False
    """
    if _is_super_admin(user):
        return True

    if _is_staff(user):
        slug = user.get("admin_role_slug")
        if not slug:
            return False
        perms = _get_admin_role_permissions(slug)
        return permission_code in perms

    return False

# ──────────────────────────────────────────────────────────────────
#  PUBLIC DECORATORS
# ──────────────────────────────────────────────────────────────────


def login_required(f: Callable) -> Callable:
    """Yêu cầu đăng nhập. Redirect về trang login nếu chưa đăng nhập."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def admin_required(f: Callable) -> Callable:
    """
    Yêu cầu tài khoản có role 'admin' HOẶC 'staff'.
    - Nếu chưa đăng nhập → redirect login
    - Nếu bị suspended → redirect trang chủ
    - Nếu không đủ quyền → 403
    """

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        user_id = session.get("user_id")

        # 1. Chưa đăng nhập
        if not user_id:
            flash("Vui lòng đăng nhập tài khoản quản trị.", "warning")
            return redirect(url_for("auth.login", next=request.url))

        # 2. Lấy thông tin user từ DB (có cache per-request)
        user = _get_user_record(user_id)
        if not user:
            session.clear()
            flash("Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.", "danger")
            return redirect(url_for("auth.login"))

        # 3. Kiểm tra tài khoản bị khoá
        if user.get("is_suspended"):
            session.clear()
            flash("Tài khoản của bạn đã bị tạm khoá.", "danger")
            return redirect(url_for("products.index"))

        # 4. Kiểm tra quyền vào admin
        if not _can_access_admin(user):
            flash("Bạn không có quyền truy cập khu vực quản trị.", "danger")
            if request.is_json:
                return abort(403)
            return redirect(url_for("products.index"))

        # 5. Đồng bộ lại session role nếu DB thay đổi
        db_role = user.get("role")
        if session.get("role") != db_role:
            session["role"] = db_role
            logger.info(f"[admin_required] Cập nhật session role={db_role} cho user_id={user_id}")

        # 6. Lưu thông tin user vào g để các view dùng lại
        g.current_admin = user

        return f(*args, **kwargs)

    return decorated


def permission_required(permission_code: str):
    """
    Kiểm tra quyền cụ thể sau khi đã qua admin_required.
    - Super admin (role='admin'): luôn pass
    - Staff: kiểm tra permission_code trong admin_roles.permissions
    
    Dùng kết hợp: @admin_required -> @permission_required('orders.manage')
    """

    def decorator(f: Callable) -> Callable:

        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return abort(401)

            # Lấy user record (đã cache trong g nếu admin_required chạy trước)
            user = _get_user_record(user_id)
            if not user:
                return abort(401)

            if _has_permission(user, permission_code):
                return f(*args, **kwargs)

            logger.warning(
                f"[permission_required] user_id={user_id} role={user.get('role')} "
                f"slug={user.get('admin_role_slug')} thiếu quyền '{permission_code}'"
            )

            if request.is_json or request.method != "GET":
                return abort(403)

            flash(f"Bạn không có quyền thực hiện thao tác này ({permission_code}).", "danger")
            return redirect(url_for("admin.dashboard"))

        return decorated

    return decorator


def super_admin_required(f: Callable) -> Callable:
    """
    Chỉ cho phép Super Admin (users.role == 'admin').
    Dùng cho các tính năng nhạy cảm: quản lý phân quyền, cài đặt hệ thống.
    """

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        user_id = session.get("user_id")
        if not user_id:
            flash("Vui lòng đăng nhập.", "warning")
            return redirect(url_for("auth.login"))

        user = _get_user_record(user_id)
        if not user or not _is_super_admin(user):
            flash("Chức năng này chỉ dành cho Super Admin.", "danger")
            if request.is_json:
                return abort(403)
            return redirect(url_for("admin.dashboard"))

        return f(*args, **kwargs)

    return decorated

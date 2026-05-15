"""
app/services/rbac_service.py
=============================
RBAC Service — Dựa trên schema thực tế:
  - users.role           : 'admin' | 'staff' | 'customer'
  - users.admin_role_slug: FK -> admin_roles.slug
  - admin_roles.slug     : Primary key (text)
  - admin_roles.name     : Tên hiển thị
  - admin_roles.permissions (JSONB): ["orders.view", "products.edit", ...]

  KHÔNG dùng bảng roles/user_roles/permissions/role_permissions
  vì chúng không có trong schema thực tế.
"""

import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ── In-memory cache đơn giản (production nên dùng Redis) ──────────
_perm_cache: dict[str, list] = {}


class RBACService:
    """
    Quản lý phân quyền dựa trên admin_roles.
    """

    # ── Admin Roles CRUD ─────────────────────────────────────────

    @staticmethod
    def get_all_roles() -> list[dict]:
        """Lấy tất cả admin roles."""
        try:
            db = get_supabase()
            res = db.table("admin_roles") \
                    .select("slug, name, permissions, created_at") \
                    .order("name") \
                    .execute()
            return res.data or []
        except Exception as e:
            logger.error(f"[RBAC] get_all_roles lỗi: {e}")
            return []

    @staticmethod
    def get_role(slug: str) -> dict | None:
        """Lấy một admin role theo slug."""
        try:
            db = get_supabase()
            res = db.table("admin_roles") \
                    .select("*") \
                    .eq("slug", slug) \
                    .limit(1) \
                    .execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"[RBAC] get_role slug={slug} lỗi: {e}")
            return None

    @staticmethod
    def create_role(slug: str, name: str, permissions: list[str]) -> dict:
        """Tạo admin role mới."""
        try:
            db = get_supabase()
            res = db.table("admin_roles").insert({
                "slug": slug,
                "name": name,
                "permissions": permissions,
            }).execute()
            RBACService._invalidate_cache_for_role(slug)
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"[RBAC] create_role lỗi: {e}")
            raise

    @staticmethod
    def update_role(slug: str, name: str | None=None, permissions: list[str] | None=None) -> dict:
        """Cập nhật admin role."""
        try:
            db = get_supabase()
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if permissions is not None:
                update_data["permissions"] = permissions
            if not update_data:
                return {}
            res = db.table("admin_roles").update(update_data).eq("slug", slug).execute()
            RBACService._invalidate_cache_for_role(slug)
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"[RBAC] update_role slug={slug} lỗi: {e}")
            raise

    @staticmethod
    def delete_role(slug: str) -> bool:
        """
        Xoá admin role. Trước đó gỡ khỏi tất cả users đang dùng role này.
        """
        try:
            db = get_supabase()
            # Gỡ role khỏi users đang dùng
            db.table("users") \
              .update({"admin_role_slug": None, "role": "customer"}) \
              .eq("admin_role_slug", slug) \
              .execute()
            # Xoá role
            db.table("admin_roles").delete().eq("slug", slug).execute()
            RBACService._invalidate_cache_for_role(slug)
            return True
        except Exception as e:
            logger.error(f"[RBAC] delete_role slug={slug} lỗi: {e}")
            return False

    # ── User ↔ Role Assignment ───────────────────────────────────

    @staticmethod
    def assign_role_to_user(user_id: str, admin_role_slug: str | None) -> bool:
        """
        Gán admin role cho user.
        - admin_role_slug=None → hạ về customer (xoá quyền staff)
        - admin_role_slug=<slug> → nâng lên staff với role đó
        """
        try:
            db = get_supabase()
            if admin_role_slug:
                # Kiểm tra slug tồn tại
                role = RBACService.get_role(admin_role_slug)
                if not role:
                    logger.warning(f"[RBAC] Slug '{admin_role_slug}' không tồn tại.")
                    return False
                db.table("users").update({
                    "role": "staff",
                    "admin_role_slug": admin_role_slug,
                }).eq("id", user_id).execute()
            else:
                db.table("users").update({
                    "role": "customer",
                    "admin_role_slug": None,
                }).eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"[RBAC] assign_role user_id={user_id} lỗi: {e}")
            return False

    @staticmethod
    def revoke_staff_access(user_id: str) -> bool:
        """Thu hồi quyền staff của user, hạ về customer."""
        return RBACService.assign_role_to_user(user_id, None)

    # ── Permission Checks ────────────────────────────────────────

    @staticmethod
    def get_user_permissions(user_id: str) -> list[str]:
        """
        Lấy danh sách permission codes của user.
        - Super admin (role='admin') → trả về ['*'] (ký hiệu toàn quyền)
        - Staff → trả về permissions từ admin_role của họ
        - Khác → []
        """
        cache_key = f"perms:{user_id}"
        if cache_key in _perm_cache:
            return _perm_cache[cache_key]

        try:
            db = get_supabase()
            user_res = db.table("users") \
                         .select("role, admin_role_slug") \
                         .eq("id", user_id) \
                         .limit(1) \
                         .execute()
            if not user_res.data:
                return []

            user = user_res.data[0]
            role = user.get("role")

            if role == "admin":
                perms = ["*"]
            elif role == "staff":
                slug = user.get("admin_role_slug")
                if not slug:
                    perms = []
                else:
                    role_res = db.table("admin_roles") \
                                 .select("permissions") \
                                 .eq("slug", slug) \
                                 .limit(1) \
                                 .execute()
                    if role_res.data:
                        raw = role_res.data[0].get("permissions") or []
                        if isinstance(raw, list):
                            perms = raw
                        elif isinstance(raw, dict):
                            perms = [k for k, v in raw.items() if v]
                        else:
                            perms = []
                    else:
                        perms = []
            else:
                perms = []

            _perm_cache[cache_key] = perms
            return perms

        except Exception as e:
            logger.error(f"[RBAC] get_user_permissions user_id={user_id} lỗi: {e}")
            return []

    @staticmethod
    def has_permission(user_id: str, permission_code: str) -> bool:
        """Kiểm tra nhanh một quyền cụ thể."""
        perms = RBACService.get_user_permissions(user_id)
        return "*" in perms or permission_code in perms

    # ── Staff User Management ────────────────────────────────────

    @staticmethod
    def get_all_staff() -> list[dict]:
        """Lấy tất cả tài khoản staff (role='staff') kèm tên role."""
        try:
            db = get_supabase()
            res = db.table("users") \
                    .select("id, email, full_name, role, admin_role_slug, is_suspended, created_at") \
                    .eq("role", "staff") \
                    .order("full_name") \
                    .execute()
            return res.data or []
        except Exception as e:
            logger.error(f"[RBAC] get_all_staff lỗi: {e}")
            return []

    # ── Cache Management ─────────────────────────────────────────

    @staticmethod
    def invalidate_user_cache(user_id: str):
        """Xoá cache quyền của một user (gọi sau khi thay đổi role)."""
        _perm_cache.pop(f"perms:{user_id}", None)

    @staticmethod
    def _invalidate_cache_for_role(slug: str):
        """Xoá cache của tất cả users đang dùng role này."""
        keys_to_delete = [k for k in _perm_cache if k.startswith("perms:")]
        # Đơn giản: xoá toàn bộ cache khi role thay đổi
        for k in keys_to_delete:
            _perm_cache.pop(k, None)

# ── Danh sách permission codes chuẩn cho toàn hệ thống ───────────
# Dùng để render UI chọn quyền khi tạo/sửa admin role


AVAILABLE_PERMISSIONS = {
    "Đơn hàng": [
        {"code": "orders.view", "label": "Xem đơn hàng"},
        {"code": "orders.manage", "label": "Xử lý đơn hàng (duyệt, huỷ)"},
        {"code": "orders.export", "label": "Xuất dữ liệu đơn hàng"},
    ],
    "Sản phẩm": [
        {"code": "products.view", "label": "Xem sản phẩm"},
        {"code": "products.create", "label": "Thêm sản phẩm mới"},
        {"code": "products.edit", "label": "Chỉnh sửa sản phẩm"},
        {"code": "products.delete", "label": "Xoá sản phẩm"},
    ],
    "Khách hàng": [
        {"code": "customers.view", "label": "Xem khách hàng"},
        {"code": "customers.manage", "label": "Quản lý khách hàng (khoá, sửa)"},
    ],
    "Mã giảm giá": [
        {"code": "coupons.view", "label": "Xem mã giảm giá"},
        {"code": "coupons.manage", "label": "Tạo & quản lý mã giảm giá"},
    ],
    "Vận chuyển & Hoàn trả": [
        {"code": "shipping.view", "label": "Xem vận chuyển"},
        {"code": "shipping.manage", "label": "Quản lý vận chuyển"},
        {"code": "returns.view", "label": "Xem yêu cầu hoàn trả"},
        {"code": "returns.manage", "label": "Xử lý hoàn trả"},
    ],
    "Báo cáo": [
        {"code": "reports.view", "label": "Xem báo cáo & thống kê"},
    ],
    "Thông báo": [
        {"code": "notifications.manage", "label": "Quản lý thông báo"},
    ],
    "POS": [
        {"code": "pos.access", "label": "Truy cập POS bán hàng tại quầy"},
    ],
    "Cài đặt": [
        {"code": "settings.view", "label": "Xem cài đặt hệ thống"},
        {"code": "settings.manage", "label": "Thay đổi cài đặt hệ thống"},
    ],
}

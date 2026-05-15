"""
app/controllers/admin/permissions_controller.py
Quản lý vai trò (Roles) và Phân quyền (Permissions) cho hệ thống Admin.
"""
import logging
from flask import render_template, request, jsonify
from app.middleware.auth_required import super_admin_required
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService
from app.utils.supabase_client import get_supabase
from ._blueprint import admin_bp

logger = logging.getLogger(__name__)

# Phân nhóm quyền dạng Dictionary chuẩn để UI dễ dàng render (bao gồm cả icon)
AVAILABLE_PERMISSIONS = {
    "Đơn hàng & Vận chuyển": [
        {"code": "orders.view", "name": "Xem đơn hàng", "icon": "fa-eye"},
        {"code": "orders.manage", "name": "Quản lý đơn hàng", "icon": "fa-pen"},
        {"code": "orders.export", "name": "Xuất file đơn hàng", "icon": "fa-file-export"},
        {"code": "shipping.view", "name": "Xem vận chuyển", "icon": "fa-eye"},
        {"code": "shipping.manage", "name": "Quản lý vận chuyển", "icon": "fa-truck"},
        {"code": "returns.view", "name": "Xem đổi trả", "icon": "fa-eye"},
        {"code": "returns.manage", "name": "Quản lý đổi trả", "icon": "fa-rotate-left"},
    ],
    "Sản phẩm & Khách hàng": [
        {"code": "products.view", "name": "Xem sản phẩm", "icon": "fa-eye"},
        {"code": "products.create", "name": "Tạo sản phẩm", "icon": "fa-plus"},
        {"code": "products.edit", "name": "Sửa sản phẩm", "icon": "fa-pen"},
        {"code": "products.delete", "name": "Xóa sản phẩm", "icon": "fa-trash"},
        {"code": "customers.view", "name": "Xem khách hàng", "icon": "fa-eye"},
        {"code": "customers.manage", "name": "Quản lý khách hàng", "icon": "fa-users-cog"},
    ],
    "Khuyến mãi, POS & Hệ thống": [
        {"code": "coupons.view", "name": "Xem khuyến mãi", "icon": "fa-eye"},
        {"code": "coupons.manage", "name": "Quản lý khuyến mãi", "icon": "fa-tags"},
        {"code": "reports.view", "name": "Xem báo cáo", "icon": "fa-chart-line"},
        {"code": "notifications.manage", "name": "Quản lý thông báo", "icon": "fa-bell"},
        {"code": "pos.access", "name": "Truy cập POS (Bán tại quầy)", "icon": "fa-cash-register"},
        {"code": "settings.view", "name": "Xem cài đặt hệ thống", "icon": "fa-cogs"},
        {"code": "settings.manage", "name": "Thay đổi cài đặt hệ thống", "icon": "fa-wrench"},
    ]
}

PROTECTED_ROLES = ["admin", "super_admin"]


@admin_bp.route("/permissions")
@super_admin_required
def permissions_index():
    roles = RBACService.get_all_roles()
    
    db = get_supabase()
    staff_res = db.table("users").select("id, email, full_name, role, admin_role_slug, is_suspended").in_("role", ["staff", "admin"]).execute()
    staff = staff_res.data or []
    
    for s in staff:
        s["initials"] = s["full_name"][0].upper() if s.get("full_name") else "?"
        s["avatar_bg"] = "bg-stone-200"
        s["avatar_fg"] = "text-stone-700"
        if s["role"] == "admin":
            s["role"] = "Super Admin"
        elif s["admin_role_slug"]:
            s["role"] = s["admin_role_slug"]
            
    stats = {
        "total_roles": len(roles),
        "protected_count": len([r for r in roles if r["slug"] in PROTECTED_ROLES]),
        "total_staff": len(staff),
        "total_permissions": sum(len(perms) for perms in AVAILABLE_PERMISSIONS.values())
    }

    return render_template("admin/roles/index.html",
                           roles=roles,
                           available_permissions=AVAILABLE_PERMISSIONS,
                           protected_roles=PROTECTED_ROLES,
                           staff=staff,
                           stats=stats)


@admin_bp.route("/roles/create", methods=["POST"])
@super_admin_required
def create_role():
    data = request.get_json()
    slug = data.get("slug", "").strip()
    name = data.get("name", "").strip()
    permissions = data.get("permissions", [])
    
    if not slug or not name:
        return jsonify({"success": False, "message": "Thiếu thông tin bắt buộc."})
        
    if RBACService.create_role(slug, name, permissions):
        AuditService.log_action("CREATE_ROLE", "admin_roles", slug, new_values=data)
        return jsonify({"success": True, "message": "Tạo nhóm quyền thành công."})
    return jsonify({"success": False, "message": "Lỗi tạo nhóm quyền hoặc định danh (slug) đã tồn tại."})


@admin_bp.route("/roles/<slug>/update", methods=["POST"])
@super_admin_required
def update_role(slug):
    if slug in PROTECTED_ROLES:
        return jsonify({"success": False, "message": "Không thể sửa nhóm quyền mặc định."})
        
    data = request.get_json()
    name = data.get("name", "").strip()
    permissions = data.get("permissions", [])
    
    if RBACService.update_role(slug, name, permissions):
        AuditService.log_action("UPDATE_ROLE", "admin_roles", slug, new_values=data)
        return jsonify({"success": True, "message": "Cập nhật thành công."})
    return jsonify({"success": False, "message": "Lỗi cập nhật."})


@admin_bp.route("/roles/<slug>/delete", methods=["POST"])
@super_admin_required
def delete_role(slug):
    if slug in PROTECTED_ROLES:
        return jsonify({"success": False, "message": "Không thể xóa nhóm quyền mặc định."})
        
    if RBACService.delete_role(slug):
        AuditService.log_action("DELETE_ROLE", "admin_roles", slug)
        return jsonify({"success": True, "message": "Đã xóa nhóm quyền."})
    return jsonify({"success": False, "message": "Lỗi xóa nhóm quyền."})


@admin_bp.route("/roles/assign", methods=["POST"])
@super_admin_required
def assign_role():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    role_slug = data.get("role_slug")
    
    if not role_slug:
        return jsonify({"success": False, "message": "Vui lòng chọn vai trò."})
        
    db = get_supabase()

    # Xử lý trường hợp thêm nhân viên mới bằng Email (chưa có user_id)
    if email and not user_id:
        user_res = db.table("users").select("id").eq("email", email.strip()).single().execute()
        if not user_res.data:
            return jsonify({"success": False, "message": f"Không tìm thấy tài khoản nào có Email: {email}"})
        user_id = user_res.data["id"]

    if not user_id:
        return jsonify({"success": False, "message": "Thiếu thông tin định danh người dùng."})
        
    if RBACService.assign_role_to_user(user_id, role_slug):
        AuditService.log_action("ASSIGN_ROLE", "users", user_id, new_values={"admin_role_slug": role_slug})
        return jsonify({"success": True, "message": "Cấp phát quyền thành công!"})
        
    return jsonify({"success": False, "message": "Lỗi hệ thống khi gán quyền."})


@admin_bp.route("/roles/revoke", methods=["POST"])
@super_admin_required
def revoke_role():
    data = request.get_json()
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Thiếu user_id để thu hồi."})
        
    if RBACService.revoke_staff_access(user_id):
        AuditService.log_action("REVOKE_ROLE", "users", user_id)
        return jsonify({"success": True, "message": "Đã thu hồi quyền truy cập."})
        
    return jsonify({"success": False, "message": "Lỗi khi thu hồi quyền."})

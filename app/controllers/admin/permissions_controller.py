"""
app/controllers/admin/permissions_controller.py
Quản lý vai trò (roles), quyền (permissions) và gán cho user.
"""
import logging
from flask import render_template, request, jsonify
from app.middleware.auth_required import admin_required
# Sửa import: permission_required nằm trong app.middleware.permissions
from app.middleware.permissions import permission_required
from app.utils.supabase_client import get_supabase
from ._blueprint import admin_bp
from ._helpers import _db

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
#  Trang chính quản lý phân quyền (chỉ super admin)
# ------------------------------------------------------------
@admin_bp.route("/permissions")
@admin_required
@permission_required("admin")  # chỉ super admin mới vào được
def permissions_index():
    db = _db()
    roles = db.table("roles").select("*").order("id").execute().data or []
    perms = db.table("permissions").select("*, permission_groups(name as group_name)") \
            .order("group_id", "code").execute().data or []
    users_with_roles = db.table("user_roles") \
        .select("user_id, role_id, users(full_name, email)") \
        .execute().data or []
    return render_template("admin/permissions/index.html",
                           roles=roles,
                           permissions=perms,
                           users_with_roles=users_with_roles)


# ------------------------------------------------------------
#  API CRUD Roles (JSON)
# ------------------------------------------------------------
@admin_bp.route("/permissions/roles", methods=["GET"])
@admin_required
def api_roles():
    db = _db()
    roles = db.table("roles").select("*").order("id").execute().data or []
    return jsonify(roles)


@admin_bp.route("/permissions/roles", methods=["POST"])
@admin_required
def api_create_role():
    data = request.get_json()
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Tên vai trò không được để trống"}), 400
    db = _db()
    try:
        res = db.table("roles").insert({"name": name, "description": description, "is_active": True}).execute()
        return jsonify({"success": True, "role": res.data[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/permissions/roles/<int:role_id>", methods=["PUT"])
@admin_required
def api_update_role(role_id):
    data = request.get_json()
    update_data = {}
    if "name" in data:
        update_data["name"] = data["name"].strip()
    if "description" in data:
        update_data["description"] = data["description"].strip()
    if "is_active" in data:
        update_data["is_active"] = bool(data["is_active"])
    if not update_data:
        return jsonify({"success": False, "error": "No data"}), 400
    db = _db()
    try:
        res = db.table("roles").update(update_data).eq("id", role_id).execute()
        return jsonify({"success": True, "role": res.data[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/permissions/roles/<int:role_id>", methods=["DELETE"])
@admin_required
def api_delete_role(role_id):
    db = _db()
    try:
        db.table("user_roles").delete().eq("role_id", role_id).execute()
        db.table("role_permissions").delete().eq("role_id", role_id).execute()
        db.table("roles").delete().eq("id", role_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
#  Gán quyền cho role (role_permissions)
# ------------------------------------------------------------
@admin_bp.route("/permissions/role-permissions/<int:role_id>", methods=["GET"])
@admin_required
def api_role_permissions(role_id):
    db = _db()
    perms = db.table("role_permissions").select("permission_id").eq("role_id", role_id).execute().data or []
    perm_ids = [p["permission_id"] for p in perms]
    return jsonify(perm_ids)


@admin_bp.route("/permissions/role-permissions/<int:role_id>", methods=["POST"])
@admin_required
def api_sync_role_permissions(role_id):
    data = request.get_json()
    perm_ids = data.get("permission_ids", [])
    db = _db()
    try:
        db.table("role_permissions").delete().eq("role_id", role_id).execute()
        if perm_ids:
            inserts = [{"role_id": role_id, "permission_id": pid} for pid in perm_ids]
            db.table("role_permissions").insert(inserts).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
#  Gán role cho user
# ------------------------------------------------------------
@admin_bp.route("/permissions/user-roles/<user_id>", methods=["GET"])
@admin_required
def api_user_roles(user_id):
    db = _db()
    roles = db.table("user_roles").select("role_id").eq("user_id", user_id).execute().data or []
    role_ids = [r["role_id"] for r in roles]
    return jsonify(role_ids)


@admin_bp.route("/permissions/user-roles/<user_id>", methods=["POST"])
@admin_required
def api_sync_user_roles(user_id):
    data = request.get_json()
    role_ids = data.get("role_ids", [])
    db = _db()
    try:
        db.table("user_roles").delete().eq("user_id", user_id).execute()
        if role_ids:
            inserts = [{"user_id": user_id, "role_id": rid} for rid in role_ids]
            db.table("user_roles").insert(inserts).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
#  Danh sách user có thể gán quyền (chỉ admin)
# ------------------------------------------------------------
@admin_bp.route("/permissions/users")
@admin_required
def api_admin_users():
    db = _db()
    users = db.table("users").select("id, email, full_name").order("full_name").execute().data or []
    return jsonify(users)

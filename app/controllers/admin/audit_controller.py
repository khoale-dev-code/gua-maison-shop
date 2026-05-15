"""
app/controllers/admin/audit_controller.py
"""
from flask import render_template, request
from app.middleware.auth_required import super_admin_required
from app.services.audit_service import AuditService
from app.services.rbac_service import RBACService
from ._blueprint import admin_bp

@admin_bp.route("/audit-logs")
@super_admin_required
def audit_logs():
    role_slug = request.args.get("role", "").strip()
    page = request.args.get("page", 1, type=int)
    
    # Lấy danh sách Role để hiển thị bộ lọc
    roles = RBACService.get_all_roles()
    
    # Lấy log 7 ngày qua
    logs_data = AuditService.get_recent_logs(days=7, role_slug=role_slug, page=page, per_page=40)
    
    return render_template(
        "admin/audit/index.html",
        logs=logs_data["items"],
        total=logs_data["total"],
        total_pages=logs_data["total_pages"],
        current_page=page,
        roles=roles,
        current_role=role_slug
    )
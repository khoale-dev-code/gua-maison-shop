from functools import wraps
from flask import session, jsonify, abort, request
from app.services.rbac_service import RBACService


def require_permission(permission_code: str):
    """Decorator kiểm tra quyền của User trước khi chạy Controller"""

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            tenant_id = session.get("tenant_id")  # Cực kỳ quan trọng cho Multi-tenant
            
            if not user_id or not tenant_id:
                return jsonify({"error": "Unauthorized"}), 401

            # Lấy tập hợp quyền (Đã được tối ưu qua Cache)
            user_perms = RBACService.get_user_permissions(user_id, tenant_id)
            
            # Super Admin (code: '*') luôn có quyền
            if '*' in user_perms or permission_code in user_perms:
                return f(*args, **kwargs)
                
            # Log lại hành vi truy cập trái phép
            import logging
            logging.warning(f"[Security] User {user_id} cố truy cập quyền {permission_code} nhưng bị từ chối.")
            
            if request.is_json:
                return jsonify({"error": "Forbidden", "message": "Bạn không có quyền thực hiện thao tác này."}), 403
            return abort(403)
            
        return decorated_function

    return decorator

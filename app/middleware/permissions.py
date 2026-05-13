# app/middleware/permissions.py (đã có sẵn, chỉ cần dùng)
from functools import wraps
from flask import session, jsonify, abort
from app.services.rbac_service import RBACService


def permission_required(permission_code: str):

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401
            # Lấy role từ session (đã được lưu lúc login)
            # Nếu role là 'admin' (super) thì cho qua, nếu không thì kiểm tra permission
            if session.get("role") == "admin":
                return f(*args, **kwargs)
            # Nếu không, kiểm tra quyền cụ thể qua service
            perms = RBACService.get_user_permissions(user_id, session.get("tenant_id", ""))
            if permission_code in perms:
                return f(*args, **kwargs)
            return jsonify({"error": "Forbidden", "message": f"Missing permission: {permission_code}"}), 403

        return decorated_function

    return decorator

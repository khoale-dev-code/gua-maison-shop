"""
app/middleware/auth_required.py
Decorator bảo vệ route – Đăng nhập và Phân quyền Admin
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from typing import Callable, Any


def login_required(f: Callable) -> Callable:
    """Bắt buộc phải đăng nhập"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def admin_required(f: Callable) -> Callable:
    """Chỉ cho phép tài khoản có role = 'admin' truy cập"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        # Kiểm tra đã đăng nhập chưa
        if "user_id" not in session:
            flash("Vui lòng đăng nhập bằng tài khoản quản trị.", "warning")
            return redirect(url_for("auth.login", next=request.url))

        # Kiểm tra quyền Admin
        if session.get("role") != "admin":
            flash("Bạn không có quyền truy cập trang quản trị.", "danger")
            
            # Quan trọng: Với POST request → trả về 403 thay vì redirect
            if request.method == "POST":
                return abort(403)  # Hoặc return jsonify({"error": "Forbidden"}), 403

            # Với GET request → redirect về trang an toàn
            return redirect(url_for("products.index"))  # hoặc url_for("home.index")

        return f(*args, **kwargs)

    return decorated

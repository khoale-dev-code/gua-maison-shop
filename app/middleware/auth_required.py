"""
app/middleware/auth_required.py
================================
Decorator bảo vệ route – yêu cầu đăng nhập và phân quyền.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request
from typing import Callable, Any


def login_required(f: Callable) -> Callable:
    """Bắt buộc user phải đăng nhập trước khi vào route."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            # Lưu lại URL người dùng muốn truy cập vào tham số 'next'
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def admin_required(f: Callable) -> Callable:
    """Chỉ admin (role='admin') mới được truy cập."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            flash("Vui lòng đăng nhập bằng tài khoản quản trị.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        
        if session.get("role") != "admin":
            flash("Bạn không có quyền truy cập trang này.", "danger")
            # Có thể truyền thêm mã lỗi HTTP (ví dụ: 403) nếu route này được gọi qua API/AJAX
            return redirect(url_for("products.index"))
            
        return f(*args, **kwargs)

    return decorated

"""
app/controllers/auth_controller.py
====================================
Phần _fetch_role và _set_session được viết lại để đọc đúng
từ cột users.role thay vì bảng user_roles (không tồn tại).
"""

import re
import logging
from urllib.parse import urlparse, urljoin
from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash, current_app)
from app.models.user_model import UserModel
from app.utils.supabase_client import get_supabase
from itsdangerous import URLSafeTimedSerializer
from app.services.email_service import send_password_reset_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_RE = re.compile(r"^[^\@\s]+@[^\@\s]+\.[^\@\s]+$")
logger = logging.getLogger(__name__)


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _fetch_role(user: dict) -> str:
    """
    Lấy role từ dict user (đã query từ DB).
    - 'admin'    → Super Admin
    - 'staff'    → Nhân viên có phân quyền
    - 'customer' → Khách hàng (mặc định)

    Không cần query thêm DB vì role đã có trong bảng users.
    """
    role = user.get("role") or "customer"
    # Chỉ chấp nhận các giá trị hợp lệ
    if role not in ("admin", "staff", "customer"):
        logger.warning(f"[auth] User id={user.get('id')} có role không hợp lệ: '{role}', fallback về 'customer'")
        return "customer"
    return role


def _set_session(user: dict, remember: bool=False):
    """Thiết lập session sau khi đăng nhập thành công."""
    session.clear()
    session.permanent = remember
    session["user_id"] = str(user["id"])
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    session["role"] = _fetch_role(user)
    # Lưu admin_role_slug vào session để dùng cho RBAC (staff)
    session["admin_role_slug"] = user.get("admin_role_slug")
    logger.info(f"[LOGIN] User {user['email']} | role={session['role']} | admin_role_slug={session.get('admin_role_slug')}")

# ═══════════════════════════════════════════════════════════════
#  REGISTER
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(
            url_for("admin.dashboard") if session.get("role") in ("admin", "staff")
            else url_for("products.index")
        )

    errors = {}

    if request.method == "POST":
        form = request.form
        full_name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")

        if not full_name:
            errors["full_name"] = "Vui lòng nhập họ tên."
        if not email or not EMAIL_RE.match(email):
            errors["email"] = "Email không hợp lệ."
        if len(password) < 6:
            errors["password"] = "Mật khẩu tối thiểu 6 ký tự."
        if password != confirm:
            errors["confirm_password"] = "Mật khẩu xác nhận không khớp."

        # Kiểm tra email đã tồn tại
        if not errors:
            existing = UserModel.get_by_email(email)
            if existing:
                errors["email"] = "Email này đã được sử dụng."

        if not errors:
            user = UserModel.create(email=email, password=password, full_name=full_name)
            if user:
                _set_session(user)
                flash("Đăng ký thành công! Chào mừng bạn.", "success")
                return redirect(url_for("products.index"))
            else:
                flash("Đăng ký thất bại. Vui lòng thử lại.", "danger")

    return render_template("auth/register.html", errors=errors)

# ═══════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(
            url_for("admin.dashboard") if session.get("role") in ("admin", "staff")
            else url_for("products.index")
        )

    error = None

    if request.method == "POST":
        form = request.form
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        remember = bool(form.get("remember"))

        user = UserModel.authenticate(email, password)

        if user:
            if user.get("is_suspended"):
                error = "Tài khoản của bạn đã bị tạm khoá. Vui lòng liên hệ hỗ trợ."
            else:
                _set_session(user, remember=remember)
                flash(f"Chào mừng trở lại, {user['full_name']}!", "success")

                next_url = request.args.get("next")
                if next_url and _is_safe_url(next_url):
                    return redirect(next_url)

                if session.get("role") in ("admin", "staff"):
                    return redirect(url_for("admin.dashboard"))
                return redirect(url_for("products.index"))
        else:
            error = "Email hoặc mật khẩu không chính xác."

    return render_template("auth/login.html", error=error)

# ═══════════════════════════════════════════════════════════════
#  LOGOUT
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/logout")
def logout():
    email = session.get("email", "unknown")
    session.clear()
    logger.info(f"[LOGOUT] {email}")
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))

# ═══════════════════════════════════════════════════════════════
#  FORGOT / RESET PASSWORD
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = UserModel.get_by_email(email)
        # Luôn hiện thông báo thành công để tránh leak email tồn tại
        if user:
            try:
                s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
                token = s.dumps(email, salt="password-reset-salt")
                reset_url = url_for("auth.reset_password", token=token, _external=True)
                send_password_reset_email(email, reset_url)
            except Exception as e:
                logger.error(f"[forgot_password] Lỗi gửi email: {e}")
        flash("Nếu email tồn tại, chúng tôi đã gửi link đặt lại mật khẩu.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
        flash("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("Mật khẩu tối thiểu 6 ký tự.", "danger")
        elif password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "danger")
        else:
            from app.utils.security import hash_password
            db = get_supabase()
            db.table("users").update({"password_hash": hash_password(password)}).eq("email", email).execute()
            flash("Đặt lại mật khẩu thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)

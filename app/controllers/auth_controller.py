"""
app/controllers/auth_controller.py
Cung cấp luồng xác thực toàn diện: Register, Login, Logout, Password Recovery.
"""

import re
import logging
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models.user_model import UserModel

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Khởi tạo Logger để truy vết bảo mật (Audit Trail)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  HELPERS & SECURITY
# ═══════════════════════════════════════════════════════════════


def _get_clean_form():
    """Helper giúp IDE (PyDev/Pylance) nhận diện request.form không bị lỗi."""
    return request.form


def _is_safe_url(target):
    """
    Ngăn chặn lỗ hổng Open Redirect. 
    Chỉ cho phép redirect về các URL nội bộ của hệ thống.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def _set_session(user: dict, remember: bool=False):
    """Thiết lập phiên làm việc và tùy chọn Remember Me."""
    session.clear()  # Dọn dẹp session cũ để tránh session fixation
    
    # Kích hoạt Remember Me
    session.permanent = remember 
    
    session["user_id"] = str(user["id"])
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    session["role"] = user.get("role", "customer")
    
    logger.info(f"Audit [LOGIN SUCCESS]: User {user['email']} (Role: {session['role']})")

# ═══════════════════════════════════════════════════════════════
#  REGISTER
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Phân luồng nếu đã đăng nhập
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("products.index"))

    errors = {}

    if request.method == "POST":
        form = _get_clean_form()
        full_name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")

        # 1. Validation cơ bản
        if not full_name or len(full_name) < 2:
            errors["full_name"] = "Vui lòng nhập họ tên đầy đủ."
        if not email or not EMAIL_RE.match(email):
            errors["email"] = "Định dạng email không hợp lệ."
        if not password or len(password) < 8:
            errors["password"] = "Mật khẩu bảo mật phải có ít nhất 8 ký tự."
        if password != confirm:
            errors["confirm_password"] = "Xác nhận mật khẩu không khớp."

        # 2. Xử lý nghiệp vụ nếu không có lỗi Input
        if not errors:
            try:
                if UserModel.email_exists(email):
                    errors["email"] = "Email này đã thuộc về một thành viên Maison."
                    logger.warning(f"Audit [REGISTER FAIL]: Duplicate email attempt - {email}")
                else:
                    user = UserModel.create(email, password, full_name)
                    if user:
                        logger.info(f"Audit [REGISTER SUCCESS]: New account created - {email}")
                        _set_session(user, remember=False)
                        flash(f"🎉 Chào mừng {full_name} gia nhập GUA Maison!", "success")
                        return redirect(url_for("products.index"))
                    else:
                        flash("Hệ thống gián đoạn. Vui lòng thử lại sau.", "danger")
            except Exception as ex:
                logger.error(f"System Error during registration: {str(ex)}")
                flash(f"Lỗi tạo tài khoản: {str(ex)}", "danger")

        return render_template("auth/register.html", errors=errors, form=form)

    return render_template("auth/register.html", errors={}, form={})

# ═══════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Phân luồng nếu đã đăng nhập
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("products.index"))

    errors = {}

    if request.method == "POST":
        form = _get_clean_form()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        remember = form.get("remember", "off") == "on"

        if not email:
            errors["email"] = "Vui lòng cung cấp email."
        if not password:
            errors["password"] = "Vui lòng nhập mật khẩu."

        if not errors:
            try:
                user = UserModel.authenticate(email, password)
                if user:
                    _set_session(user, remember=remember)
                    flash(f"Chào mừng trở lại, {user['full_name']}.", "success")
                    
                    role = user.get("role", "customer")
                    next_url = request.args.get("next")
                    
                    # Ưu tiên 1: Phân luồng an toàn cho Admin
                    if role == "admin":
                        # Chỉ giữ next_url nếu nó thực sự dẫn vào khu vực /admin/
                        if next_url and next_url.startswith("/admin") and _is_safe_url(next_url):
                            return redirect(next_url)
                        return redirect(url_for("admin.dashboard"))
                    
                    # Ưu tiên 2: Customer có next_url (ví dụ: đang mua hàng bị yêu cầu đăng nhập)
                    if next_url and _is_safe_url(next_url):
                        return redirect(next_url)
                    
                    # Ưu tiên 3: Mặc định cho Customer về Storefront
                    return redirect(url_for("products.index"))
                
                else:
                    logger.warning(f"Audit [LOGIN FAIL]: Invalid credentials for {email}")
                    # Kiểm tra xem do sai pass hay email không tồn tại
                    try:
                        existing = UserModel.get_by_email(email)
                        if existing is None:
                            errors["general"] = f"Không tìm thấy tài khoản với email '{email}'."
                        else:
                            errors["general"] = "Mật khẩu không đúng."
                    except Exception:
                        errors["general"] = "Email hoặc mật khẩu không chính xác."
                    
            except Exception as ex:
                logger.error(f"Database Auth Error: {str(ex)}")
                flash(f"Lỗi kết nối máy chủ xác thực: {str(ex)}", "danger")

        return render_template("auth/login.html", errors=errors, form=form)

    return render_template("auth/login.html", errors={}, form={})

# ═══════════════════════════════════════════════════════════════
#  PASSWORD RECOVERY (FORGOT / RESET)
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Luồng yêu cầu khôi phục mật khẩu."""
    if request.method == "POST":
        form = _get_clean_form()
        email = form.get("email", "").strip().lower()
        
        if not email or not EMAIL_RE.match(email):
            flash("Vui lòng nhập email hợp lệ.", "danger")
        else:
            try:
                # Todo: Gọi model tạo token và gửi Email
                logger.info(f"Audit [PW RECOVERY]: Requested for {email}")
                
                # Luôn báo thành công để chống dò quét email (Email Enumeration Attack)
                flash("Nếu email hợp lệ, hướng dẫn khôi phục sẽ được gửi đến hộp thư của bạn.", "info")
                return redirect(url_for("auth.login"))
            except Exception as ex:
                logger.error(f"Recovery error: {str(ex)}")
                flash("Lỗi hệ thống.", "danger")
                
    return render_template("auth/forgot_password.html")

# ═══════════════════════════════════════════════════════════════
#  LOGOUT
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    name = session.get("full_name", "")
    email = session.get("email", "Unknown")
    
    logger.info(f"Audit [LOGOUT]: User {email} logged out.")
    session.clear()
    
    flash(f"Đã đăng xuất an toàn. Hẹn gặp lại{(' ' + name.split()[0]) if name else ''}.", "info")
    return redirect(url_for("auth.login"))

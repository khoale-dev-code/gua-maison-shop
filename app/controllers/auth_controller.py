"""
app/controllers/auth_controller.py
"""

import re
import logging
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models.user_model import UserModel
from app.utils.supabase_client import get_supabase
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

# ✅ Import email service mới
from app.services.email_service import send_password_reset_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logger = logging.getLogger(__name__)


def _get_clean_form():
    return request.form


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def _fetch_role(user_id: str) -> str:
    """
    Lấy role của user bằng 2 bước riêng biệt (tránh lỗi join Supabase client).
    Trả về 'admin' hoặc 'customer'.
    """
    try:
        db = get_supabase()

        # Bước 1: Lấy danh sách role_id của user
        ur_res = db.table("user_roles").select("role_id").eq("user_id", user_id).execute()
        if not ur_res.data:
            logger.warning(f"[RBAC] user_id={user_id} không có bản ghi nào trong user_roles.")
            return "customer"

        role_ids = [row["role_id"] for row in ur_res.data]
        logger.debug(f"[RBAC] user_id={user_id} có role_ids={role_ids}")

        # Bước 2: Lấy tên role từ bảng roles theo các role_id vừa có
        roles_res = db.table("roles").select("id, name").in_("id", role_ids).execute()
        if not roles_res.data:
            logger.warning(f"[RBAC] Không tìm thấy roles với ids={role_ids}")
            return "customer"

        role_names = [row["name"] for row in roles_res.data]
        logger.debug(f"[RBAC] user_id={user_id} có role_names={role_names}")

        return "admin" if "admin" in role_names else "customer"

    except Exception as e:
        logger.error(f"[RBAC Error] Lỗi fetch role cho user_id={user_id}: {e}")
        return "customer"


def _set_session(user: dict, remember: bool=False):
    session.clear()
    session.permanent = remember
    session["user_id"] = str(user["id"])
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    session["role"] = _fetch_role(str(user["id"]))
    logger.info(f"Audit [LOGIN SUCCESS]: User {user['email']} (Role: {session['role']})")

# ═══════════════════════════════════════════════════════════════
#  REGISTER
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard") if session.get("role") == "admin" else url_for("products.index"))

    errors = {}

    if request.method == "POST":
        form = _get_clean_form()
        full_name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")

        if not full_name or len(full_name) < 2:
            errors["full_name"] = "Vui lòng nhập họ tên đầy đủ."
        if not email or not EMAIL_RE.match(email):
            errors["email"] = "Định dạng email không hợp lệ."
        if not password or len(password) < 8:
            errors["password"] = "Mật khẩu phải có ít nhất 8 ký tự."
        if password != confirm:
            errors["confirm_password"] = "Xác nhận mật khẩu không khớp."

        if not errors:
            try:
                if UserModel.email_exists(email):
                    errors["email"] = "Email này đã thuộc về một thành viên Maison."
                    logger.warning(f"Audit [REGISTER FAIL]: Duplicate email - {email}")
                else:
                    user = UserModel.create(email, password, full_name)
                    if user:
                        logger.info(f"Audit [REGISTER SUCCESS]: {email}")
                        _set_session(user, remember=False)
                        flash(f"🎉 Chào mừng {full_name} gia nhập GUA Maison!", "success")
                        return redirect(url_for("products.index"))
                    else:
                        flash("Hệ thống gián đoạn. Vui lòng thử lại sau.", "danger")
            except Exception as ex:
                logger.error(f"Registration error: {ex}")
                flash(f"Lỗi tạo tài khoản: {ex}", "danger")

        return render_template("auth/register.html", errors=errors, form=form)

    return render_template("auth/register.html", errors={}, form={})

# ═══════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard") if session.get("role") == "admin" else url_for("products.index"))

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

                    role = session.get("role", "customer")
                    next_url = request.args.get("next")

                    if role == "admin":
                        if next_url and next_url.startswith("/admin") and _is_safe_url(next_url):
                            return redirect(next_url)
                        return redirect(url_for("admin.dashboard"))

                    if next_url and _is_safe_url(next_url):
                        return redirect(next_url)

                    return redirect(url_for("products.index"))

                else:
                    logger.warning(f"Audit [LOGIN FAIL]: {email}")
                    try:
                        existing = UserModel.get_by_email(email)
                        errors["general"] = (
                            f"Không tìm thấy tài khoản với email '{email}'." if existing is None
                            else "Mật khẩu không đúng."
                        )
                    except Exception:
                        errors["general"] = "Email hoặc mật khẩu không chính xác."

            except Exception as ex:
                logger.error(f"Database Auth Error: {ex}")
                flash("Lỗi kết nối máy chủ. Vui lòng thử lại sau.", "danger")

        return render_template("auth/login.html", errors=errors, form=form)

    return render_template("auth/login.html", errors={}, form={})

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

# ═══════════════════════════════════════════════════════════════
#  FORGOT PASSWORD (GỬI LINK KHÔI PHỤC)
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("products.index"))

    if request.method == "POST":
        form = _get_clean_form()
        email = form.get("email", "").strip().lower()

        if not email or not EMAIL_RE.match(email):
            flash("Vui lòng nhập email hợp lệ.", "danger")
        else:
            try:
                user = UserModel.get_by_email(email)
                if user:
                    # 1. Tạo Token bảo mật sống trong 1 giờ
                    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                    token = s.dumps(email, salt='gua-password-reset')

                    # 2. Tạo link khôi phục
                    # Ưu tiên dùng BASE_URL từ .env (domain production Vercel)
                    # Fallback về url_for khi dev local
                    base_url = current_app.config.get("BASE_URL", "").rstrip("/")
                    if base_url:
                        reset_link = f"{base_url}/auth/reset-password/{token}"
                    else:
                        reset_link = url_for("auth.reset_password", token=token, _external=True)

                    # ✅ 3. Gửi email thật qua Gmail SMTP
                    sent = send_password_reset_email(
                        recipient_email=email,
                        recipient_name=user.get("full_name", ""),
                        reset_link=reset_link,
                    )

                    if sent:
                        logger.info(f"Audit [PW RESET EMAIL SENT]: {email}")
                        flash("Thành công! Link khôi phục đã được gửi đến email của bạn.", "success")
                    else:
                        # Gửi thất bại — log link để admin debug, không lộ ra ngoài
                        logger.error(
                            f"[PW RESET] SendGrid thất bại cho {email}. "
                            f"Reset link (internal): {reset_link}"
                        )
                        flash(
                            "Không thể gửi email lúc này. Vui lòng thử lại sau hoặc liên hệ hỗ trợ.",
                            "danger",
                        )
                        return render_template("auth/forgot_password.html")

                else:
                    # Chống dò quét Email: luôn báo thành công dù email không tồn tại
                    logger.info(f"[PW RESET] Email không tồn tại (silently ignored): {email}")
                    flash(
                        "Nếu email hợp lệ, hướng dẫn khôi phục sẽ được gửi đến hộp thư của bạn.",
                        "info",
                    )

                return redirect(url_for("auth.login"))

            except Exception as e:
                logger.error(f"Forgot password error: {e}")
                flash("Hệ thống đang bận. Vui lòng thử lại sau.", "danger")

    return render_template("auth/forgot_password.html")

# ═══════════════════════════════════════════════════════════════
#  RESET PASSWORD (ĐẶT LẠI MẬT KHẨU MỚI)
# ═══════════════════════════════════════════════════════════════


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if "user_id" in session:
        return redirect(url_for("products.index"))

    # 1. Giải mã và kiểm tra thời hạn Token
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # max_age=3600 nghĩa là link chỉ sống trong 1 giờ
        email = s.loads(token, salt='gua-password-reset', max_age=3600)
    except Exception:
        flash("Link khôi phục đã hết hạn hoặc không hợp lệ. Vui lòng yêu cầu lại.", "danger")
        return redirect(url_for("auth.forgot_password"))

    # 2. Xử lý đặt mật khẩu mới
    if request.method == "POST":
        form = _get_clean_form()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")

        if not password or len(password) < 8:
            flash("Mật khẩu mới phải có ít nhất 8 ký tự.", "danger")
        elif password != confirm:
            flash("Xác nhận mật khẩu không khớp.", "danger")
        else:
            try:
                user = UserModel.get_by_email(email)
                if user:
                    from app.utils.security import hash_password
                    # Lưu mật khẩu mới vào DB
                    get_supabase().table("users").update({
                        "password_hash": hash_password(password)
                    }).eq("email", email).execute()

                    logger.info(f"Audit [PW RESET SUCCESS]: {email}")
                    flash("Mật khẩu đã được thay đổi thành công! Vui lòng đăng nhập lại.", "success")
                    return redirect(url_for("auth.login"))
            except Exception as e:
                logger.error(f"Reset password error: {e}")
                flash("Lỗi kết nối cơ sở dữ liệu. Vui lòng thử lại.", "danger")

    return render_template("auth/reset_password.html", token=token)

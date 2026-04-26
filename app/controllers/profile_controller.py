"""
app/controllers/profile_controller.py
Quản lý hồ sơ cá nhân, bảo mật tài khoản và lịch sử giao dịch khách hàng.
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, session, flash, abort, request

from app.models.user_model import UserModel
from app.models.order_model import OrderModel
from app.utils.security import hash_password, verify_password
from app.middleware.auth_required import login_required

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  DASHBOARD CÁ NHÂN
# ═══════════════════════════════════════════════════════════════


@profile_bp.route("/")
@login_required
def index():
    """Trang quản trị tổng hợp cho khách hàng (Client Overview)."""
    user_id = session.get("user_id")
    try:
        user = UserModel.get_by_id(user_id)
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))

        # Lấy danh sách đơn hàng để tính toán stats
        orders = OrderModel.get_user_orders(user_id)
        
        # Thống kê nhanh theo DNA Industrial Matrix
        stats = {
            "total": len(orders),
            "pending": sum(1 for o in orders if o.get("status") == "pending"),
            "delivered": sum(1 for o in orders if o.get("status") == "delivered"),
            "spent": sum(float(o.get("total_amount", 0)) for o in orders if o.get("status") != "cancelled"),
        }
        
        # Chỉ hiển thị 5 đơn hàng mới nhất ở Dashboard
        return render_template("profile/index.html", user=user, orders=orders[:5], stats=stats)
    except Exception as e:
        logger.error(f"Critical Error in Profile Index: {e}")
        return abort(500)

# ═══════════════════════════════════════════════════════════════
#  LỊCH SỬ ĐƠN HÀNG (ARCHIVE)
# ═══════════════════════════════════════════════════════════════


@profile_bp.route("/orders")
@login_required
def orders():
    """Danh sách toàn bộ đơn hàng đã thực hiện (Paginated)."""
    user_id = session.get("user_id")
    try:
        page = request.args.get("page", 1, type=int)
        # Sử dụng hàm Model có phân trang để tối ưu tốc độ load
        result = OrderModel.get_user_orders_paginated(user_id, page=page, per_page=10)
        
        return render_template("profile/orders.html",
                               orders=result.get("items", []),
                               pagination=result.get("pagination", {}))
    except Exception as e:
        logger.warning(f"Pagination failed, falling back to full list: {e}")
        all_orders = OrderModel.get_user_orders(user_id)
        return render_template("profile/orders.html", orders=all_orders, pagination=None)


@profile_bp.route("/orders/<order_id>")
@login_required
def order_detail(order_id):
    """
    CHI TIẾT ĐƠN HÀNG - Sửa lỗi 404.
    Hệ thống sẽ verify quyền sở hữu trước khi hiển thị.
    """
    user_id = session.get("user_id")
    try:
        order = OrderModel.get_by_id(order_id)
        
        # BẢO MẬT: Kiểm tra IDOR (Chặn xem đơn hàng của người khác)
        if not order or str(order.get("user_id")) != str(user_id):
            logger.warning(f"Unauthorized access attempt: User {user_id} -> Order {order_id}")
            flash("Không tìm thấy dữ liệu đơn hàng hoặc quyền truy cập bị từ chối.", "danger")
            return redirect(url_for("profile.orders"))

        return render_template("profile/order_detail.html", order=order)
    except Exception as e:
        logger.error(f"Error loading order detail {order_id}: {e}")
        abort(404)

# ═══════════════════════════════════════════════════════════════
#  QUẢN LÝ THÔNG TIN (SECURITY & DATA)
# ═══════════════════════════════════════════════════════════════


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    """Cập nhật dữ liệu cá nhân."""
    user_id = session.get("user_id")
    user = UserModel.get_by_id(user_id)

    if request.method == "POST":
        form_data = request.form
        full_name = form_data.get("full_name", "").strip()
        phone = form_data.get("phone", "").strip()

        if not full_name or len(full_name) < 2:
            flash("Định dạng tên không hợp lệ (Tối thiểu 2 ký tự).", "danger")
            return render_template("profile/edit.html", user=user)

        try:
            update_data = {"full_name": full_name, "phone": phone}
            if UserModel.update_profile(user_id, update_data):
                session["full_name"] = full_name
                flash("Hồ sơ Maison đã được đồng bộ hóa.", "success")
                return redirect(url_for("profile.index"))
        except Exception as e:
            logger.error(f"Profile Sync Failed: {e}")
            flash("Lỗi kết nối máy chủ dữ liệu.", "danger")

    return render_template("profile/edit.html", user=user)


@profile_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Cấp lại mật khẩu mới."""
    if request.method == "POST":
        data = request.form
        current = data.get("current_password", "")
        new_pwd = data.get("new_password", "")
        confirm = data.get("confirm_password", "")
        user_id = session.get("user_id")

        try:
            user = UserModel.get_by_id(user_id)
            if not verify_password(current, user.get("password_hash", "")):
                flash("Xác thực mật khẩu hiện tại thất bại.", "danger")
                return render_template("profile/change_password.html")

            if len(new_pwd) < 8 or new_pwd != confirm:
                flash("Mật khẩu mới không khớp hoặc không đủ độ mạnh (Min 8 ký tự).", "danger")
                return render_template("profile/change_password.html")

            if UserModel.update_profile(user_id, {"password_hash": hash_password(new_pwd)}):
                flash("Mật khẩu đã được thay đổi an toàn.", "success")
                return redirect(url_for("profile.index"))
        except Exception as e:
            logger.error(f"Security Update Failed: {e}")
            flash("Hệ thống bảo mật đang bận.", "danger")

    return render_template("profile/change_password.html")

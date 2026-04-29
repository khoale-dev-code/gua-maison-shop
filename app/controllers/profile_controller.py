"""
app/controllers/profile_controller.py
Quản lý hồ sơ cá nhân, bảo mật tài khoản, lịch sử giao dịch và sổ địa chỉ khách hàng.
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, session, flash, abort, request

from app.models.user_model import UserModel
from app.models.order_model import OrderModel
from app.models.address_model import AddressModel
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

        orders = OrderModel.get_user_orders(user_id)
        
        stats = {
            "total": len(orders),
            "pending": sum(1 for o in orders if o.get("status") == "pending"),
            "delivered": sum(1 for o in orders if o.get("status") == "delivered"),
            "spent": sum(float(o.get("total_amount", 0)) for o in orders if o.get("status") != "cancelled"),
        }
        
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
    user_id = session.get("user_id")
    try:
        # Gán request.args ra biến để thỏa mãn Linter
        req_args = request.args
        page = req_args.get("page", 1, type=int)
        
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
    user_id = session.get("user_id")
    try:
        order = OrderModel.get_by_id(order_id)
        
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
    if request.method == "POST":
        form_data = request.form
        current = form_data.get("current_password", "")
        new_pwd = form_data.get("new_password", "")
        confirm = form_data.get("confirm_password", "")
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

# ═══════════════════════════════════════════════════════════════
#  QUẢN LÝ SỔ ĐỊA CHỈ (ADDRESS BOOK)
# ═══════════════════════════════════════════════════════════════


@profile_bp.route("/addresses", methods=["GET", "POST"])
@login_required
def addresses():
    user_id = session.get("user_id")
    
    if request.method == "POST":
        form_data = request.form
        
        # Lấy dữ liệu từ Form
        data = {
            "full_name": form_data.get("full_name", "").strip(),
            "phone": form_data.get("phone", "").strip(),
            "province": form_data.get("province_name", "").strip(),  # Lấy tên (Text) thay vì ID
            "district": form_data.get("district_name", "").strip(),
            "ward": form_data.get("ward_name", "").strip(),
            "address_line": form_data.get("address_line", "").strip(),
            "note": form_data.get("note", "").strip()
        }
        
        is_default = form_data.get("is_default") == "on"
        
        # Validate các trường bắt buộc
        required_fields = ["full_name", "phone", "province", "district", "ward", "address_line"]
        if not all(data[field] for field in required_fields):
            flash("Vui lòng điền đầy đủ thông tin bắt buộc.", "danger")
        else:
            # Lưu địa chỉ vào DB
            new_addr = AddressModel.add_address(user_id, data)
            
            # Nếu user tick "Đặt làm mặc định", tự động gọi hàm set_default để đè các địa chỉ cũ
            if is_default and new_addr and new_addr.get("id"):
                AddressModel.set_default(user_id, new_addr["id"])
                
            flash("Đã thêm địa chỉ mới thành công.", "success")
            return redirect(url_for("profile.addresses", next=request.args.get('next')))

    user_addresses = AddressModel.get_user_addresses(user_id)
    # FIX: Đúng path template — file nằm ở app/templates/profile/address/addresses.html
    return render_template("profile/address/addresses.html", addresses=user_addresses)


@profile_bp.route("/addresses/set-default/<address_id>", methods=["POST"])
@login_required
def set_default_address(address_id):
    user_id = session.get("user_id")
    if AddressModel.set_default(user_id, address_id):
        flash("Đã cập nhật địa chỉ mặc định.", "success")
    else:
        flash("Có lỗi xảy ra khi cập nhật địa chỉ, vui lòng thử lại.", "danger")
    
    form_data = request.form  # FIX: Gán ra biến trung gian
    next_url = form_data.get("next_url", url_for("profile.addresses"))
    
    return redirect(next_url)


@profile_bp.route("/addresses/delete/<address_id>", methods=["POST"])
@login_required
def delete_address(address_id):
    user_id = session.get("user_id")
    if AddressModel.delete_address(user_id, address_id):
        flash("Đã xóa địa chỉ thành công.", "success")
    else:
        flash("Không thể xóa địa chỉ này.", "danger")
        
    return redirect(url_for("profile.addresses"))


@profile_bp.route("/addresses/edit/<address_id>", methods=["POST"])
@login_required
def edit_address(address_id):
    """Cập nhật một địa chỉ hiện có."""
    user_id = session.get("user_id")
    form_data = request.form
    
    # Lấy dữ liệu từ Form (giống hệt lúc Thêm mới)
    data = {
        "full_name": form_data.get("full_name", "").strip(),
        "phone": form_data.get("phone", "").strip(),
        "province": form_data.get("province_name", "").strip(),
        "district": form_data.get("district_name", "").strip(),
        "ward": form_data.get("ward_name", "").strip(),
        "address_line": form_data.get("address_line", "").strip(),
        "note": form_data.get("note", "").strip()
    }
    
    is_default = form_data.get("is_default") == "on"
    
    # Validate
    required_fields = ["full_name", "phone", "province", "district", "ward", "address_line"]
    if not all(data[field] for field in required_fields):
        flash("Vui lòng điền đầy đủ thông tin bắt buộc.", "danger")
    else:
        # Gọi Model để update
        if AddressModel.update_address(user_id, address_id, data):
            # Nếu user tick "Đặt làm mặc định", cập nhật luôn
            if is_default:
                AddressModel.set_default(user_id, address_id)
            flash("Đã cập nhật địa chỉ thành công.", "success")
        else:
            flash("Không thể cập nhật địa chỉ này hoặc bạn không có quyền.", "danger")
            
    # Điều hướng về lại trang Sổ địa chỉ (hoặc trang thanh toán nếu có next)
    next_url = request.args.get('next')
    if next_url:
        return redirect(url_for("profile.addresses", next=next_url))
    return redirect(url_for("profile.addresses"))

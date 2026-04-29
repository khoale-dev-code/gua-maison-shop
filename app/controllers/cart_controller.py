"""
app/controllers/cart_controller.py
Quản lý Giỏ hàng và Luồng Thanh toán (Checkout) chuẩn E-commerce 2026
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.models.cart_model import CartModel
from app.models.order_model import OrderModel
from app.models.address_model import AddressModel  # Import Model Địa chỉ
from app.middleware.auth_required import login_required

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")
logger = logging.getLogger(__name__)


def calculate_cart_total(items):
    """Hàm helper tính tổng tiền giỏ hàng."""
    return sum(
        item["quantity"] * item["products"]["price"] 
        for item in items if item.get("products")
    )

# ═══════════════════════════════════════════════════════════════
#  QUẢN LÝ GIỎ HÀNG
# ═══════════════════════════════════════════════════════════════


@cart_bp.route("/")
@login_required
def view():
    """Hiển thị giỏ hàng hiện tại."""
    try:
        user_id = session.get("user_id")
        items = CartModel.get_cart(user_id)
        total = calculate_cart_total(items)
        return render_template("cart/cart.html", items=items, total=total)
    except Exception as e:
        logger.error(f"Error viewing cart: {e}")
        return render_template("cart/cart.html", items=[], total=0)


@cart_bp.route("/add", methods=["POST"])
@login_required
def add():
    """Thêm sản phẩm vào giỏ hàng và xử lý 'Mua ngay'."""
    try:
        user_id = session.get("user_id")
        form_data = request.form
        
        product_id = form_data.get("product_id")
        quantity_str = form_data.get("quantity", "1")
        quantity = int(quantity_str) if quantity_str.isdigit() else 1
        size = form_data.get("size")
        action = form_data.get("action")  # 'buy_now' hoặc 'add_to_cart'

        if not product_id:
            return jsonify({"error": "Thiếu thông tin sản phẩm"}), 400

        CartModel.add_item(user_id, product_id, quantity, size)
        
        # Luồng "Mua ngay" -> Nhảy thẳng đến Checkout
        if action == "buy_now":
            return redirect(url_for("cart.checkout"))

        # Xử lý AJAX cho nút "Thêm vào giỏ" ở Trang chủ/Cửa hàng
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "message": "Đã thêm vào giỏ hàng",
                "count": CartModel.get_count(user_id)
            })
            
        flash("Đã thêm vào giỏ hàng thành công!", "success")
        return redirect(request.referrer or url_for("cart.view"))
    except Exception as e:
        logger.error(f"Error adding to cart: {e}")
        return jsonify({"error": "Có lỗi xảy ra"}), 500


@cart_bp.route("/update/<item_id>", methods=["POST"])
@login_required
def update(item_id):
    """Cập nhật số lượng sản phẩm (Nếu <= 0 thì tự động xóa)."""
    try:
        form_data = request.form
        quantity_str = form_data.get("quantity", "1")
        quantity = int(quantity_str) if quantity_str.isdigit() else 1
        
        if quantity > 0:
            CartModel.update_quantity(item_id, quantity)
        else:
            CartModel.remove_item(item_id)  # Tự động xóa nếu user giảm SL về 0
            flash("Đã xóa sản phẩm khỏi giỏ hàng.", "info")
            
        return redirect(url_for("cart.view"))
    except Exception as e:
        logger.error(f"Error updating cart item: {e}")
        return redirect(url_for("cart.view"))


@cart_bp.route("/remove/<item_id>", methods=["POST"])
@login_required
def remove(item_id):
    """Xóa hẳn sản phẩm khỏi giỏ hàng."""
    try:
        CartModel.remove_item(item_id)
        flash("Đã xóa sản phẩm khỏi giỏ hàng.", "success")
    except Exception as e:
        logger.error(f"Error removing cart item: {e}")
        flash("Không thể xóa sản phẩm lúc này.", "danger")
    return redirect(url_for("cart.view"))

# ═══════════════════════════════════════════════════════════════
#  LUỒNG THANH TOÁN (CHECKOUT)
# ═══════════════════════════════════════════════════════════════


@cart_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    """Xử lý luồng đặt hàng liên kết với Sổ địa chỉ."""
    user_id = session.get("user_id")
    items = CartModel.get_cart(user_id)
    
    # 1. Chặn nếu giỏ hàng rỗng
    if not items:
        flash("Giỏ hàng của bạn đang trống.", "warning")
        return redirect(url_for("cart.view"))

    total = calculate_cart_total(items)

    # 2. Lấy danh sách địa chỉ của User
    addresses = AddressModel.get_user_addresses(user_id)
    
    # 3. LUỒNG CHƯA CÓ ĐỊA CHỈ: Bắt buộc sang trang Profile tạo địa chỉ
    if not addresses:
        flash("Vui lòng thiết lập địa chỉ nhận hàng để tiếp tục thanh toán.", "warning")
        # Truyền tham số next=/cart/checkout để tạo xong nó tự quay lại đây
        return redirect(url_for("profile.addresses", next=url_for("cart.checkout")))

    # 4. Lấy địa chỉ Mặc định để hiển thị ra UI
    default_address = next((addr for addr in addresses if addr.get('is_default')), addresses[0])

    # 5. KHI KHÁCH HÀNG BẤM "HOÀN TẤT ĐẶT HÀNG" (SUBMIT FORM)
    if request.method == "POST":
        form_data = request.form
        selected_address_id = form_data.get("address_id")
        note = form_data.get("note", "").strip()

        # Kiểm tra xem ID địa chỉ có hợp lệ không
        selected_address = next((addr for addr in addresses if str(addr.get("id")) == str(selected_address_id)), None)

        if not selected_address:
            flash("Vui lòng chọn địa chỉ giao hàng hợp lệ.", "danger")
            return redirect(url_for("cart.checkout"))

        # Gộp các trường địa chỉ (Số nhà, Phường, Quận, Tỉnh) thành 1 chuỗi hoàn chỉnh cho Đơn hàng
        ward = selected_address.get('ward', '')
        district = selected_address.get('district', '')
        province = selected_address.get('province', '')
        
        full_address_str = f"{selected_address.get('address_line')}, {ward}, {district}, {province}".strip(", ")
        # Xóa các dấu phẩy thừa nếu có field bị rỗng
        full_address_str = ", ".join([part.strip() for part in full_address_str.split(',') if part.strip()])

        # Đóng gói dữ liệu giao hàng
        shipping_data = {
            "full_name": selected_address.get("full_name"),
            "phone": selected_address.get("phone"),
            "address": full_address_str,
            "city": province,  # Dùng Tỉnh/Thành phố làm City
            "note": note  # Ghi chú của khách hàng
        }
        
        try:
            # Tạo Đơn hàng mới
            order = OrderModel.create_order(user_id, items, total, shipping_data)
            if order:
                # Dọn sạch giỏ hàng
                CartModel.clear_cart(user_id)
                # Chuyển tới trang Thành công
                return redirect(url_for("cart.order_success", order_id=order.get("id")))
        except Exception as e:
            logger.error(f"Checkout failed: {e}")
            flash("Có lỗi xảy ra trong quá trình xử lý đơn hàng, vui lòng thử lại.", "danger")

    # Render giao diện nếu là GET Request
    return render_template("cart/checkout.html",
                           items=items,
                           total=total,
                           default_address=default_address)


@cart_bp.route("/order-success/<order_id>")
@login_required
def order_success(order_id):
    """Trang cảm ơn và xác nhận đơn hàng."""
    return render_template("cart/order_success.html", order_id=order_id)

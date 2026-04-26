import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.models.cart_model import CartModel
from app.models.order_model import OrderModel
from app.middleware.auth_required import login_required

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")
logger = logging.getLogger(__name__)


def calculate_cart_total(items):
    """Hàm helper tính tổng tiền giỏ hàng."""
    return sum(
        item["quantity"] * item["products"]["price"] 
        for item in items if item.get("products")
    )


@cart_bp.route("/")
@login_required
def view():
    """Hiển thị giỏ hàng."""
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
        
        # Nếu là hành động "Mua ngay", chuyển hướng thẳng đến checkout
        if action == "buy_now":
            return redirect(url_for("cart.checkout"))

        # Xử lý AJAX cho nút "Thêm vào giỏ"
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
    """Cập nhật số lượng item."""
    try:
        form_data = request.form
        quantity_str = form_data.get("quantity", "1")
        quantity = int(quantity_str) if quantity_str.isdigit() else 1
        
        CartModel.update_quantity(item_id, quantity)
        return redirect(url_for("cart.view"))
    except Exception as e:
        logger.error(f"Error updating cart item: {e}")
        return redirect(url_for("cart.view"))


@cart_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    """Xử lý thanh toán."""
    user_id = session.get("user_id")
    items = CartModel.get_cart(user_id)
    
    if not items:
        flash("Giỏ hàng của bạn đang trống.", "warning")
        return redirect(url_for("cart.view"))

    total = calculate_cart_total(items)

    if request.method == "POST":
        # Gán vào biến cục bộ để fix lỗi PyDev 'Undefined get'
        form_data = request.form
        
        full_name = form_data.get("full_name", "").strip()
        phone = form_data.get("phone", "").strip()
        address = form_data.get("address", "").strip()
        city = form_data.get("city", "").strip()

        if not all([full_name, phone, address, city]):
            flash("Vui lòng điền đầy đủ thông tin giao hàng.", "danger")
            return render_template("cart/checkout.html", items=items, total=total)

        shipping_data = {
            "full_name": full_name,
            "phone": phone,
            "address": address,
            "city": city
        }
        
        try:
            order = OrderModel.create_order(user_id, items, total, shipping_data)
            if order:
                CartModel.clear_cart(user_id)
                return redirect(url_for("cart.order_success", order_id=order["id"]))
        except Exception as e:
            logger.error(f"Checkout failed: {e}")
            
        flash("Có lỗi xảy ra, vui lòng thử lại.", "danger")

    return render_template("cart/checkout.html", items=items, total=total)


@cart_bp.route("/order-success/<order_id>")
@login_required
def order_success(order_id):
    return render_template("cart/order_success.html", order_id=order_id)

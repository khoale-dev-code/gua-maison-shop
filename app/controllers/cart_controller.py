"""
app/controllers/cart_controller.py
Quản lý Giỏ hàng, Luồng Thanh toán (Checkout) và Khuyến mãi (Coupons) chuẩn E-commerce 2026.
Tích hợp thanh toán VNPay, Voucher và Kiến trúc Biến thể (Variants).
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.models.cart_model import CartModel
from app.models.order_model import OrderModel
from app.models.address_model import AddressModel
from app.services.vnpay_service import VNPayService
from app.middleware.auth_required import login_required
from app.utils.supabase_client import get_supabase

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def calculate_cart_total(items: list) -> float:
    """
    Tính tổng giá trị hàng hóa trong giỏ (chưa trừ voucher).
    CẬP NHẬT: Ưu tiên lấy Giá của Biến thể (nếu Admin có set giá riêng), 
    nếu không thì lấy Giá gốc của Sản phẩm.
    """
    total = 0.0
    for item in items:
        qty = int(item.get("quantity", 0))
        variant = item.get("product_variants") or {}
        product = item.get("products") or {}
        
        # Lấy giá trị override của variant, nếu None thì fallback về giá gốc
        price = variant.get("price_override")
        if price is None:
            price = product.get("price", 0)
            
        total += qty * float(price)
    return total


def _get_user_id():
    return str(session.get("user_id"))

# ═══════════════════════════════════════════════════════════════
#  GIỎ HÀNG (Cart Management)
# ═══════════════════════════════════════════════════════════════


@cart_bp.route("/")
@login_required
def index():
    user_id = _get_user_id()
    try:
        items = CartModel.get_user_cart(user_id)
        total = calculate_cart_total(items)
        return render_template("cart/cart.html", items=items, total=total)
    except Exception as e:
        logger.error(f"Lỗi tải giỏ hàng: {e}")
        flash("Đã xảy ra lỗi khi tải giỏ hàng.", "danger")
        return redirect(url_for("home.index"))


@cart_bp.route("/add", methods=["POST"])
@login_required
def add_to_cart():
    user_id = _get_user_id()
    data = dict(request.form)
    
    product_id = data.get("product_id")
    variant_id = data.get("variant_id")  # Mã định danh cho cặp Size - Màu
    
    try:
        quantity = int(data.get("quantity", 1))
    except ValueError:
        quantity = 1

    # Rào cản số 1: Validate đầu vào cực chặt
    if not product_id or not variant_id:
        flash("Vui lòng chọn đầy đủ Màu sắc và Kích thước trước khi thêm vào túi hàng.", "warning")
        return redirect(request.referrer or url_for("shop.index"))

    if quantity <= 0:
        flash("Số lượng mua không hợp lệ.", "warning")
        return redirect(request.referrer or url_for("shop.index"))

    try:
        # Gọi Model lưu trực tiếp với Variant ID
        res = CartModel.add_item(user_id=user_id, product_id=product_id, variant_id=variant_id, quantity=quantity)
        if res:
            flash("Sản phẩm đã được thêm vào túi hàng thành công!", "success")
        else:
            flash("Không thể lưu sản phẩm vào túi hàng. Vui lòng thử lại.", "danger")
    except Exception as e:
        logger.error(f"Lỗi add_to_cart backend: {e}")
        flash("Hệ thống đang bận, thao tác chưa thành công.", "danger")

    return redirect(request.referrer or url_for("cart.index"))


@cart_bp.route("/update/<item_id>", methods=["POST"])
@login_required
def update_quantity(item_id: str):
    user_id = _get_user_id()
    try:
        quantity = int(dict(request.form).get("quantity", 1))
        if quantity <= 0:
            CartModel.remove_item(user_id, item_id)
        else:
            CartModel.update_quantity(user_id, item_id, quantity)
    except ValueError:
        flash("Dữ liệu cập nhật số lượng không hợp lệ.", "danger")
    except Exception as e:
        logger.error(f"Lỗi cập nhật số lượng giỏ hàng: {e}")
        flash("Đã xảy ra lỗi khi cập nhật số lượng.", "danger")

    return redirect(url_for("cart.index"))


@cart_bp.route("/remove/<item_id>", methods=["POST"])
@login_required
def remove_item(item_id):
    user_id = _get_user_id()
    try:
        success = CartModel.remove_item(user_id, item_id)
        if success:
            flash("Đã loại bỏ sản phẩm khỏi túi hàng.", "success")
        else:
            flash("Không tìm thấy sản phẩm này trong giỏ.", "danger")
    except Exception as e:
        logger.error(f"Lỗi xóa item giỏ hàng: {e}")
        flash("Lỗi hệ thống khi xóa sản phẩm.", "danger")
        
    return redirect(url_for("cart.index"))

# ═══════════════════════════════════════════════════════════════
#  KHUYẾN MÃI (COUPONS)
# ═══════════════════════════════════════════════════════════════


@cart_bp.route("/apply-coupon", methods=["POST"])
@login_required
def apply_coupon():
    """Kiểm tra mã giảm giá từ Giao diện Checkout bằng AJAX."""
    user_id = _get_user_id()
    req_data = request.get_json() or {}
    coupon_code = req_data.get("code", "").strip().upper()
    
    if not coupon_code:
        return jsonify({"valid": False, "error": "Vui lòng nhập mã khuyến mãi."})

    try:
        db = get_supabase()
        items = CartModel.get_user_cart(user_id)
        if not items:
            return jsonify({"valid": False, "error": "Giỏ hàng của bạn đang trống."})
        
        # Truy vấn Coupon
        res = db.table("coupons").select("*").eq("code", coupon_code).eq("is_active", True).single().execute()
        coupon = res.data
        
        if not coupon:
            return jsonify({"valid": False, "error": "Mã giảm giá không tồn tại hoặc đã hết hạn."})
            
        cart_total = calculate_cart_total(items)
        if cart_total < float(coupon.get("min_order_value", 0)):
            return jsonify({
                "valid": False,
                "error": f"Mã này áp dụng cho đơn hàng từ {int(coupon['min_order_value']):,}đ"
            })

        # Logic tính toán giảm giá
        discount = 0
        val = float(coupon.get("discount_value", 0))
        if coupon["discount_type"] == "percent":
            discount = cart_total * (val / 100)
            if coupon.get("max_discount"):
                discount = min(discount, float(coupon["max_discount"]))
        else:
            discount = val
        
        # Chặn lỗi giảm giá lớn hơn cả giá trị đơn
        discount = min(discount, cart_total)
        
        return jsonify({
            "valid": True,
            "discount": discount,
            "final_total": cart_total - discount,
            "coupon_id": coupon["id"],
            "code": coupon["code"]
        })

    except Exception as e:
        logger.error(f"Lỗi apply_coupon: {e}")
        return jsonify({"valid": False, "error": "Hệ thống khuyến mãi đang bận, vui lòng thử lại."})

# ═══════════════════════════════════════════════════════════════
#  THANH TOÁN (CHECKOUT)
# ═══════════════════════════════════════════════════════════════


@cart_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    user_id = _get_user_id()
    items = CartModel.get_user_cart(user_id)
    
    if not items:
        flash("Vui lòng chọn sản phẩm trước khi thanh toán.", "warning")
        return redirect(url_for("shop.index"))

    total = calculate_cart_total(items)
    addresses = AddressModel.get_user_addresses(user_id)
    default_address = next((a for a in addresses if a.get("is_default")), addresses[0] if addresses else None)

    if request.method == "POST":
        form = dict(request.form)
        address_id = form.get("address_id")
        payment_method = form.get("payment_method", "COD").upper()
        order_notes = form.get("order_notes", "").strip()
        coupon_code = form.get("coupon_code", "").strip().upper()

        # 1. Bóc tách địa chỉ giao hàng
        selected_address = next((a for a in addresses if str(a["id"]) == address_id), default_address)
        if not selected_address:
            flash("Vui lòng thiết lập địa chỉ giao hàng trước khi thanh toán.", "danger")
            return redirect(url_for("profile.addresses"))

        address_snapshot = {
            "full_name": selected_address.get("full_name"),
            "phone": selected_address.get("phone"),
            "address": selected_address.get("address_line"),
            "ward": selected_address.get("ward"),
            "district": selected_address.get("district"),
            "city": selected_address.get("province"),
        }

        # 2. Re-Validate Khuyến mãi tại Server (Bảo mật 100%)
        discount_amount = 0
        coupon_id = None
        if coupon_code:
            try:
                db = get_supabase()
                c_res = db.table("coupons").select("*").eq("code", coupon_code).eq("is_active", True).single().execute()
                coupon = c_res.data
                if coupon and total >= float(coupon.get("min_order_value", 0)):
                    coupon_id = coupon["id"]
                    if coupon["discount_type"] == "percent":
                        discount_amount = total * (float(coupon["discount_value"]) / 100)
                        if coupon.get("max_discount"):
                            discount_amount = min(discount_amount, float(coupon["max_discount"]))
                    else:
                        discount_amount = float(coupon["discount_value"])
                    discount_amount = min(discount_amount, total)
            except Exception as e:
                logger.warning(f"Bỏ qua mã giảm giá do lỗi server hoặc mã sai: {e}")

        final_total = total - discount_amount

        try:
            # 3. Khởi tạo Đơn hàng mới
            order = OrderModel.create_order(
                user_id=user_id,
                items=items,
                total=final_total,
                address=address_snapshot,
                payment_method=payment_method,
                order_notes=order_notes
            )

            if not order:
                flash("Lỗi tạo đơn hàng. Vui lòng liên hệ CSKH.", "danger")
                return redirect(url_for("cart.checkout"))

            order_id = str(order["id"])

            # 4. Ghi lại Lịch sử dùng Voucher
            if coupon_id:
                try:
                    get_supabase().table("coupon_usages").insert({
                        "coupon_id": coupon_id,
                        "user_id": user_id,
                        "order_id": order_id,
                        "discount_amount": discount_amount
                    }).execute()
                except Exception as e:
                    logger.error(f"Lỗi ghi nhận lịch sử coupon: {e}")

            # 5. Phân luồng Cổng thanh toán
            if payment_method == "VNPAY":
                vnpay_url = VNPayService.create_payment_url(
                    order_id=order_id,
                    amount=final_total,
                    ip_address=request.remote_addr or "127.0.0.1",
                    order_desc=f"Thanh toan hoa don GUA {order_id[:8].upper()}"
                )
                return redirect(vnpay_url)

            # Nếu là COD: Xóa giỏ hàng và Dẫn tới trang Hoàn tất
            CartModel.clear_cart(user_id)
            flash("🎉 Đơn hàng của bạn đã được ghi nhận thành công!", "success")
            return redirect(url_for("cart.order_success", order_id=order_id))

        except Exception as e:
            logger.exception(f"Checkout system error: {e}")
            flash("Đã xảy ra lỗi nghiêm trọng khi xử lý đơn hàng. Vui lòng thử lại.", "danger")

    return render_template(
        "cart/checkout.html",
        items=items,
        total=total,
        default_address=default_address,
        addresses=addresses
    )


@cart_bp.route("/order-success/<order_id>")
@login_required
def order_success(order_id):
    order = OrderModel.get_by_id(order_id)
    if not order:
        return redirect(url_for("home.index"))
    return render_template("cart/order_success.html", order=order)

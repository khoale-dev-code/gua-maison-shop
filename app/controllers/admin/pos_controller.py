"""
app/controllers/admin/pos_controller.py
Xử lý chuyên biệt cho hệ thống Máy Bán Hàng Tại Quầy (POS).
"""

import logging
from datetime import datetime
from flask import render_template, request, jsonify

from app.middleware.auth_required import admin_required
from ._blueprint import admin_bp
from ._helpers import handle_errors

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  GIAO DIỆN POS TERMINAL
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos")
@admin_required
@handle_errors("Lỗi tải trang POS.", "admin.dashboard")
def pos_terminal():
    """Tải dữ liệu Sản phẩm & Mã giảm giá để hiển thị trên máy POS"""
    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        
        # 1. Lấy danh sách sản phẩm (có hình ảnh và biến thể)
        p_res = db.table("products").select(
            "id, name, price, stock, thumbnail_url, product_variants(id, size, color_name, color_hex, stock, price_override)"
        ).eq("is_active", True).is_("deleted_at", "null").order("name").execute()
        
        # 2. Lấy danh sách mã giảm giá hợp lệ
        now_iso = datetime.now().isoformat()
        c_res = db.table("coupons").select(
            "id, code, discount_type, discount_value, max_discount, min_order_value"
        ).eq("is_active", True).or_(f"expires_at.is.null,expires_at.gt.{now_iso}").execute()

        products = p_res.data if p_res.data else []
        coupons = c_res.data if c_res.data else []
        
    except Exception as e:
        logger.error(f"[pos_terminal] Lỗi lấy dữ liệu DB: {e}")
        products, coupons = [], []

    return render_template(
        "admin/pos_terminal.html",
        products=products,
        coupons=coupons
    )


# ═══════════════════════════════════════════════════════════════
#  XỬ LÝ THANH TOÁN (CHECKOUT)
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-checkout", methods=["POST"])
@admin_required
def pos_checkout():
    """Xử lý mảng giỏ hàng, tạo đơn hàng POS và trừ kho"""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    discount = float(data.get("discount", 0))

    if not items:
        return jsonify({"success": False, "message": "Giỏ hàng trống!"})

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        
        subtotal = sum(float(item["price"]) * int(item["quantity"]) for item in items)
        total = max(0, subtotal - discount)
        
        # Sinh mã đơn hàng chuẩn POS
        order_code = f"POS{datetime.now().strftime('%y%m%d%H%M%S')}"
        
        # 1. Tạo đơn hàng chính
        order_data = {
            "code": order_code,
            "customer_name": "Khách mua tại quầy",
            "source": "pos",
            "status": "completed",
            "payment_status": "paid",
            "payment_method": "cash",
            "total_amount": total,
            "shipping_fee": 0,
            "discount_amount": discount       
        }
        
        order_res = db.table("orders").insert(order_data).execute()
        order_id = order_res.data[0]["id"]
        
        # 2. Xử lý từng sản phẩm trong giỏ (Lưu items & Trừ kho)
        for item in items:
            qty = int(item["quantity"])
            
            # Lưu Order Item
            db.table("order_items").insert({
                "order_id": order_id,
                "product_id": item["product_id"],
                "variant_id": item.get("variant_id"),
                "quantity": qty,
                "unit_price": float(item["price"])
            }).execute()
            
            # Trừ kho Variant (Nếu có)
            if item.get("variant_id"):
                v_res = db.table("product_variants").select("stock").eq("id", item["variant_id"]).execute()
                if v_res.data:
                    new_stock = max(0, v_res.data[0]["stock"] - qty)
                    db.table("product_variants").update({"stock": new_stock}).eq("id", item["variant_id"]).execute()
            # Trừ kho Product gốc (Nếu không có variant)
            else:
                p_res = db.table("products").select("stock").eq("id", item["product_id"]).execute()
                if p_res.data:
                    new_stock = max(0, p_res.data[0]["stock"] - qty)
                    db.table("products").update({"stock": new_stock}).eq("id", item["product_id"]).execute()
                    
        logger.info(f"[POS Checkout] Thành công đơn {order_code} - {total:,.0f}đ")
                    
        return jsonify({
            "success": True,
            "invoice": {
                "order_code": order_code,
                "date": datetime.now().strftime('%d/%m/%Y %H:%M'),
                "items": [{"name": i["name"], "qty": i["quantity"], "price": float(i["price"])} for i in items],
                "subtotal": subtotal,
                "discount": discount,
                "total": total
            }
        })
        
    except Exception as e:
        logger.error(f"[pos_checkout] Lỗi hệ thống: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi thanh toán."})

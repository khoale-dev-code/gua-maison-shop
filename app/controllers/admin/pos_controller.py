"""
app/controllers/admin/pos_controller.py
Xử lý hệ thống Máy Bán Hàng Tại Quầy (POS).

Tích hợp:
  - Bán hàng, trừ tồn kho tự động.
  - Sổ cái Loyalty (Ledger): Kiểm tra SĐT, dùng điểm giảm giá (Redeem) và tích điểm (Earn).
  - Casso webhook: tự động duyệt đơn & bắn lệnh tích điểm khi nhận được tiền.
"""

import logging
import os
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

from flask import render_template, request, jsonify

from app.middleware.auth_required import admin_required
from ._blueprint import admin_bp
from ._helpers import handle_errors

logger = logging.getLogger(__name__)

CASSO_SECRET = os.environ.get("CASSO_SECRET_KEY", "")
STORE_ACCOUNT = "4890440016335294"

# ═══════════════════════════════════════════════════════════════
#  QUY TẮC TÍCH / TIÊU ĐIỂM
# ═══════════════════════════════════════════════════════════════
BASE_EARN_RATE = 10000  # 10.000 VNĐ = 1 điểm (Tích lũy)
POINT_REDEEM_VALUE = 100  # 1 điểm = 100 VNĐ (Quy đổi giảm giá)


def calculate_points(amount: float) -> int:
    return int(amount / BASE_EARN_RATE)


# ═══════════════════════════════════════════════════════════════
#  1. API: TRA CỨU KHÁCH HÀNG BẰNG SĐT (Dùng cho giao diện POS)
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-lookup-customer", methods=["POST"])
@admin_required
def pos_lookup_customer():
    """Tra cứu SĐT xem có phải thành viên không, trả về số điểm hiện có."""
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    
    if not phone:
        return jsonify({"success": False, "message": "Vui lòng nhập SĐT"})
        
    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        res = db.table("users").select("id, full_name, points, member_tier").eq("phone", phone).execute()
        
        if res.data:
            user = res.data[0]
            return jsonify({
                "success": True,
                "name": user.get("full_name"),
                "points": user.get("points") or 0,
                "tier": user.get("member_tier") or "MEMBER"
            })
        return jsonify({"success": False, "message": "Khách chưa có tài khoản thành viên."})
    except Exception as e:
        logger.error(f"[pos_lookup_customer] Lỗi: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống tra cứu."})


# ═══════════════════════════════════════════════════════════════
#  2. GIAO DIỆN POS TERMINAL
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos")
@admin_required
@handle_errors("Lỗi tải trang POS.", "admin.dashboard")
def pos_terminal():
    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()

        p_res = db.table("products").select(
            "id, name, price, stock, thumbnail_url, barcode, "
            "product_variants(id, size, color_name, color_hex, stock, price_override)"
        ).eq("is_active", True).is_("deleted_at", "null").order("name").execute()

        now_iso = datetime.now().isoformat()
        c_res = db.table("coupons").select(
            "id, code, discount_type, discount_value, max_discount, min_order_value"
        ).eq("is_active", True).or_(f"expires_at.is.null,expires_at.gt.{now_iso}").execute()

        products = p_res.data or []
        coupons = c_res.data or []

    except Exception as e:
        logger.error(f"[pos_terminal] Lỗi lấy dữ liệu DB: {e}")
        products, coupons = [], []

    return render_template("admin/pos/pos_terminal.html", products=products, coupons=coupons)


# ═══════════════════════════════════════════════════════════════
#  3. TẠO ĐƠN HÀNG (CHECKOUT) - CÓ DÙNG ĐIỂM & TÍCH ĐIỂM
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-checkout", methods=["POST"])
@admin_required
def pos_checkout():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    method = data.get("payment_method", "cash")
    coupon_id = data.get("coupon_id") or None
    discount_from_coupon = float(data.get("discount", 0))  # Giảm từ mã voucher
    
    # Dữ liệu khách & điểm
    customer_phone = data.get("customer_phone", "").strip()
    customer_name = data.get("customer_name") or "Khách mua tại quầy"
    points_used = int(data.get("points_used", 0))  # Số điểm khách muốn tiêu

    if not items:
        return jsonify({"success": False, "message": "Giỏ hàng trống!"})
    if method not in ("cash", "transfer"):
        return jsonify({"success": False, "message": "Phương thức thanh toán không hợp lệ."})

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()

        user_id = None
        current_points = 0
        point_msg = ""
        point_discount_value = 0

        # ── A. XÁC MINH KHÁCH HÀNG & SỐ ĐIỂM ──
        if customer_phone:
            user_res = db.table("users").select("id, full_name, points").eq("phone", customer_phone).execute()
            if user_res.data:
                user_id = user_res.data[0]["id"]
                current_points = user_res.data[0].get("points") or 0
                customer_name = user_res.data[0].get("full_name") or customer_name
            else:
                # Nếu có nhập số điện thoại mà không tìm thấy trong DB
                if points_used > 0:
                    return jsonify({"success": False, "message": "SĐT chưa đăng ký tài khoản thành viên. Không thể trừ điểm!"})
                else:
                    point_msg = " (SĐT chưa đăng ký hệ thống)"

        # ── B. KIỂM TRA ĐIỀU KIỆN DÙNG ĐIỂM (REDEEM) ──
        if points_used > 0:
            if not user_id:
                return jsonify({"success": False, "message": "Khách chưa có tài khoản thành viên để dùng điểm."})
            if current_points < points_used:
                return jsonify({"success": False, "message": f"Tài khoản chỉ có {current_points} điểm. Không đủ để trừ!"})
            
            # Quy ra tiền giảm giá (VD: 100 điểm * 100đ = 10.000đ)
            point_discount_value = points_used * POINT_REDEEM_VALUE

        # ── C. TÍNH TOÁN TỔNG TIỀN ──
        subtotal = sum(float(i["price"]) * int(i["quantity"]) for i in items)
        total_discount = discount_from_coupon + point_discount_value
        total = max(0.0, subtotal - total_discount)
        
        order_code = f"POS{datetime.now().strftime('%y%m%d%H%M%S')}"
        order_status = "completed" if method == "cash" else "pending"
        payment_status = "paid"    if method == "cash" else "pending"

        # ── D. GHI SỔ CÁI: TRỪ ĐIỂM (NẾU KHÁCH CÓ DÙNG) ──
        if points_used > 0:
            db.table("loyalty_transactions").insert({
                "user_id": user_id,
                "amount":-points_used,  # Phải mang dấu ÂM
                "transaction_type": "REDEEM_POS",
                "description": f"Dùng điểm giảm giá đơn {order_code}",
                "reference_id": order_code
            }).execute()

        # ── E. GHI SỔ CÁI: CỘNG ĐIỂM LẠI TRÊN SỐ TIỀN THỰC TRẢ ──
        earned_points = calculate_points(total)
        if user_id and earned_points > 0:
            if method == "cash":
                expires_at = (datetime.now() + relativedelta(years=1)).isoformat()
                db.table("loyalty_transactions").insert({
                    "user_id": user_id,
                    "amount": earned_points,
                    "transaction_type": "EARN_POS_CASH",
                    "description": f"Tích điểm đơn {order_code}",
                    "reference_id": order_code,
                    "expires_at": expires_at
                }).execute()
                point_msg = f" (Đã dùng {points_used} điểm, tích thêm {earned_points} điểm)" if points_used > 0 else f" (Đã tích {earned_points} điểm)"
            else:
                point_msg = f" Sẽ cộng {earned_points} điểm khi nhận được tiền."

        # ── F. TẠO ĐƠN HÀNG VÀ TRỪ KHO ──
        order_res = db.table("orders").insert({
            "code": order_code,
            "user_id": user_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "sales_channel": "pos",
            "status": order_status,
            "payment_status": payment_status,
            "payment_method": method,
            "total_amount": total,
            "shipping_fee": 0,
            "discount_amount": total_discount,  # Gộp cả Voucher + Điểm
            "coupon_id": coupon_id,
        }).execute()

        order_id = order_res.data[0]["id"]

        for item in items:
            qty = int(item["quantity"])
            db.table("order_items").insert({
                "order_id": order_id,
                "product_id": item["product_id"],
                "variant_id": item.get("variant_id") or None,
                "quantity": qty,
                "unit_price": float(item["price"]),
                "product_name": item.get("name", "Sản phẩm")
            }).execute()

            # Trừ tồn kho
            if item.get("variant_id"):
                v = db.table("product_variants").select("stock").eq("id", item["variant_id"]).execute()
                if v.data: db.table("product_variants").update({"stock": max(0, v.data[0]["stock"] - qty)}).eq("id", item["variant_id"]).execute()
            else:
                p = db.table("products").select("stock").eq("id", item["product_id"]).execute()
                if p.data: db.table("products").update({"stock": max(0, p.data[0]["stock"] - qty)}).eq("id", item["product_id"]).execute()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "message": f"Thanh toán thành công.{point_msg}",
            "invoice": {
                "order_code": order_code,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "payment_method": method,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "items": [{"name": i["name"], "qty": i["quantity"], "price": float(i["price"])} for i in items],
                "subtotal": subtotal,
                "discount": total_discount,
                "total": total,
            }
        })

    except Exception as e:
        logger.error(f"[pos_checkout] Lỗi: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi thanh toán."})


# ═══════════════════════════════════════════════════════════════
#  4. POLLING & WEBHOOK CASSO (Giữ nguyên)
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-check-payment/<order_id>")
@admin_required
def pos_check_payment(order_id: str):
    try:
        from app.utils.supabase_client import get_supabase
        res = get_supabase().table("orders").select("payment_status").eq("id", order_id).execute()
        return jsonify({"paid": res.data[0]["payment_status"] == "paid" if res.data else False})
    except Exception: return jsonify({"paid": False})


@admin_bp.route("/pos-webhook-casso", methods=["POST"])
def pos_webhook_casso():
    token = request.headers.get("Secure-Token", "")
    if CASSO_SECRET and token != CASSO_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    transactions = payload.get("data", [])
    if not transactions: return jsonify({"success": True, "processed": 0})

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        processed = 0

        for txn in transactions:
            bank_acc = str(txn.get("bank_sub_acc_id", "") or txn.get("subAccId", ""))
            amount = float(txn.get("amount", 0))
            desc = str(txn.get("description", "")).upper()

            if bank_acc != STORE_ACCOUNT or amount <= 0: continue
            
            order_code = _extract_order_code(desc)
            if not order_code: continue

            res = db.table("orders").select("id, total_amount, payment_status, user_id").eq("code", order_code).eq("sales_channel", "pos").execute()
            if not res.data or res.data[0]["payment_status"] == "paid": continue
            
            order = res.data[0]
            expected = float(order["total_amount"])
            if abs(amount - expected) > 1000: continue

            # A. Gạch nợ đơn hàng
            db.table("orders").update({
                "payment_status": "paid", "status": "completed",
                "order_notes": f"Casso tự xác nhận | TID: {txn.get('tid','')} | Nhận: {amount:,.0f}đ"
            }).eq("id", order["id"]).execute()

            # B. Ghi nhận Sổ cái Tích điểm khi khách trả khoản tiền
            if order.get("user_id"):
                earned = calculate_points(expected)
                if earned > 0:
                    expires_at = (datetime.now() + relativedelta(years=1)).isoformat()
                    db.table("loyalty_transactions").insert({
                        "user_id": order["user_id"],
                        "amount": earned,
                        "transaction_type": "EARN_POS_TRANSFER",
                        "description": f"Tích điểm POS - CK {order_code}",
                        "reference_id": order_code,
                        "expires_at": expires_at
                    }).execute()

            processed += 1

        return jsonify({"success": True, "processed": processed})

    except Exception as e:
        logger.error(f"[Webhook] Lỗi: {e}")
        return jsonify({"error": "Internal error"}), 500


def _extract_order_code(description: str) -> str | None:
    match = re.search(r'POS\d{12}', description)
    return match.group(0) if match else None

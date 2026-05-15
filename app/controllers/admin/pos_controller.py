"""
app/controllers/admin/pos_controller.py
Xử lý hệ thống Máy Bán Hàng Tại Quầy (POS).

Tích hợp:
  - USB / Camera barcode scanner (xử lý phía frontend)
  - Casso webhook: tự động duyệt đơn khi Techcombank nhận được tiền
    → Cấu hình tại https://casso.vn → Webhooks → URL: /admin/pos-webhook-casso
    → Secret key lưu vào biến môi trường: CASSO_SECRET_KEY
"""

import hashlib
import hmac
import logging
import os
from datetime import datetime

from flask import render_template, request, jsonify

from app.middleware.auth_required import admin_required
from ._blueprint import admin_bp
from ._helpers import handle_errors

logger = logging.getLogger(__name__)

# Secret key lấy từ dashboard Casso (Settings → Webhook)
CASSO_SECRET = os.environ.get("CASSO_SECRET_KEY", "")

# STK Techcombank của cửa hàng
STORE_ACCOUNT = "4890440016335294"


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
#  TẠO ĐƠN HÀNG CHỜ (PENDING) – TRẢ VỀ order_id + order_code
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-checkout", methods=["POST"])
@admin_required
def pos_checkout():
    """Tạo đơn hàng POS (trạng thái pending) và trừ tồn kho."""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    discount = float(data.get("discount", 0))
    method = data.get("payment_method", "cash")  # "cash" | "transfer"
    coupon_id = data.get("coupon_id") or None

    if not items:
        return jsonify({"success": False, "message": "Giỏ hàng trống!"})
    if method not in ("cash", "transfer"):
        return jsonify({"success": False, "message": "Phương thức thanh toán không hợp lệ."})

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()

        subtotal = sum(float(i["price"]) * int(i["quantity"]) for i in items)
        total = max(0.0, subtotal - discount)
        order_code = f"POS{datetime.now().strftime('%y%m%d%H%M%S')}"

        # Tiền mặt → completed ngay; Chuyển khoản → pending chờ Casso webhook
        order_status = "completed" if method == "cash" else "pending"
        payment_status = "paid"      if method == "cash" else "pending"

        # FIX SCHEMA: Sử dụng "sales_channel" thay vì "source"
        order_res = db.table("orders").insert({
            "code": order_code,
            "customer_name": data.get("customer_name") or "Khách mua tại quầy",
            "customer_phone": data.get("customer_phone") or None,
            "sales_channel": "pos",
            "status": order_status,
            "payment_status": payment_status,
            "payment_method": method,
            "total_amount": total,
            "shipping_fee": 0,
            "discount_amount": discount,
            "coupon_id": coupon_id,
        }).execute()

        order_id = order_res.data[0]["id"]

        # ── Lưu items & trừ kho ──────────────────────────────────────
        for item in items:
            qty = int(item["quantity"])
            db.table("order_items").insert({
                "order_id": order_id,
                "product_id": item["product_id"],
                "variant_id": item.get("variant_id") or None,
                "quantity": qty,
                "unit_price": float(item["price"]),
            }).execute()

            if item.get("variant_id"):
                v = db.table("product_variants").select("stock").eq("id", item["variant_id"]).execute()
                if v.data:
                    db.table("product_variants").update(
                        {"stock": max(0, v.data[0]["stock"] - qty)}
                    ).eq("id", item["variant_id"]).execute()
            else:
                p = db.table("products").select("stock").eq("id", item["product_id"]).execute()
                if p.data:
                    db.table("products").update(
                        {"stock": max(0, p.data[0]["stock"] - qty)}
                    ).eq("id", item["product_id"]).execute()

        logger.info(f"[POS] Đơn {order_code} | {method} | {total:,.0f}đ | {order_status}")

        return jsonify({
            "success": True,
            "order_id": order_id,
            "invoice": {
                "order_code": order_code,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "payment_method": method,
                "items": [
                    {"name": i["name"], "qty": i["quantity"], "price": float(i["price"])}
                    for i in items
                ],
                "subtotal": subtotal,
                "discount": discount,
                "total": total,
            }
        })

    except Exception as e:
        logger.error(f"[pos_checkout] Lỗi hệ thống: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi thanh toán."})


# ═══════════════════════════════════════════════════════════════
#  POLLING – KIỂM TRA TRẠNG THÁI THANH TOÁN CHUYỂN KHOẢN
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-check-payment/<order_id>")
@admin_required
def pos_check_payment(order_id: str):
    """
    Frontend polling mỗi 3 giây để biết chuyển khoản đã vào chưa.
    Khi Casso webhook cập nhật payment_status='paid' thì trả về paid=True.
    """
    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        res = db.table("orders").select("payment_status, status").eq("id", order_id).execute()

        if not res.data:
            return jsonify({"paid": False})

        row = res.data[0]
        return jsonify({"paid": row["payment_status"] == "paid"})

    except Exception as e:
        logger.error(f"[pos_check_payment] {e}")
        return jsonify({"paid": False})


# ═══════════════════════════════════════════════════════════════
#  CASSO WEBHOOK – TỰ ĐỘNG DUYỆT ĐƠN KHI NHẬN TIỀN TECHCOMBANK
# ═══════════════════════════════════════════════════════════════
@admin_bp.route("/pos-webhook-casso", methods=["POST"])
def pos_webhook_casso():
    """
    Nhận callback từ Casso khi tài khoản Techcombank 4890440016335294
    nhận được giao dịch.
    """
    # ── 1. Xác thực Secure Token ──────────────────────────────────
    token = request.headers.get("Secure-Token", "")
    if CASSO_SECRET and token != CASSO_SECRET:
        logger.warning("[casso_webhook] Sai Secure-Token — bỏ qua.")
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    transactions = payload.get("data", [])

    if not transactions:
        return jsonify({"success": True, "processed": 0})

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        processed = 0

        for txn in transactions:
            # Chỉ xử lý giao dịch vào tài khoản cửa hàng (credit)
            bank_acc = str(txn.get("bank_sub_acc_id", "") or txn.get("subAccId", ""))
            amount = float(txn.get("amount", 0))
            desc = str(txn.get("description", "")).upper()

            if bank_acc != STORE_ACCOUNT or amount <= 0:
                continue

            # ── 2. Tìm order_code trong nội dung chuyển khoản ────────
            order_code = _extract_order_code(desc)
            if not order_code:
                logger.info(f"[casso_webhook] Giao dịch {txn.get('tid')} không có order_code — bỏ qua.")
                continue

            # ── 3. Tìm đơn hàng POS đang pending ─────────────────────
            # FIX SCHEMA: Sử dụng "sales_channel" thay vì "source"
            res = db.table("orders").select("id, total_amount, payment_status").eq(
                "code", order_code
            ).eq("sales_channel", "pos").execute()

            if not res.data:
                logger.warning(f"[casso_webhook] Không tìm thấy đơn {order_code}")
                continue

            order = res.data[0]

            if order["payment_status"] == "paid":
                logger.info(f"[casso_webhook] Đơn {order_code} đã paid — bỏ qua.")
                continue

            # ── 4. Kiểm tra số tiền (cho phép lệch ±1000đ do làm tròn) ──
            expected = float(order["total_amount"])
            if abs(amount - expected) > 1000:
                logger.warning(
                    f"[casso_webhook] Đơn {order_code}: nhận {amount:,.0f}đ "
                    f"nhưng cần {expected:,.0f}đ — không khớp."
                )
                continue

            # ── 5. Cập nhật trạng thái đơn hàng ──────────────────────
            db.table("orders").update({
                "payment_status": "paid",
                "status": "completed",
                "order_notes": f"Casso tự xác nhận | TID: {txn.get('tid','')} | "
                               f"Nhận: {amount:,.0f}đ lúc {txn.get('when','')}"
            }).eq("id", order["id"]).execute()

            processed += 1
            logger.info(
                f"[casso_webhook] ✓ Đơn {order_code} đã thanh toán "
                f"{amount:,.0f}đ (TID: {txn.get('tid','')})"
            )

        return jsonify({"success": True, "processed": processed})

    except Exception as e:
        logger.error(f"[casso_webhook] Lỗi xử lý: {e}")
        return jsonify({"error": "Internal server error"}), 500


def _extract_order_code(description: str) -> str | None:
    """
    Trích xuất mã đơn POS từ nội dung chuyển khoản.
    Mã đơn có dạng: POS + 12 số (VD: POS240601123456)
    """
    import re
    match = re.search(r'POS\d{12}', description)
    return match.group(0) if match else None

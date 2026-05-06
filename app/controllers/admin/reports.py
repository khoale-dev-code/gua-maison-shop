"""
app/controllers/admin/reports.py
Quản lý trang Báo cáo phân tích (Omnichannel Analytics) và API máy POS tại quầy.
"""
import logging
import uuid
from datetime import datetime
from flask import render_template, request, jsonify, session

from ._blueprint import admin_bp
from app.middleware.auth_required import admin_required
from app.models.report_model import ReportModel
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def _get_products_and_coupons(db):
    products_res = (
        db.table("products")
        .select("id, name, price, stock, product_variants(id, size, color_name, color_hex, stock, price_override)")
        .eq("is_active", True)
        .is_("deleted_at", "null")
        .order("name")
        .execute()
    )
    products = products_res.data or []

    now_str = datetime.now().isoformat()
    coupons_res = (
        db.table("coupons")
        .select("id, code, discount_type, discount_value, max_discount, min_order_value")
        .eq("is_active", True)
        .or_(f"expires_at.is.null,expires_at.gt.{now_str}")
        .execute()
    )
    coupons = coupons_res.data or []

    return products, coupons


@admin_bp.route("/reports", methods=["GET"])
@admin_required
def reports():
    report_data = ReportModel.get_dashboard_reports()
    stats = {"monthly": report_data.get("monthly_stats", [])}

    db = get_supabase()
    products, coupons = _get_products_and_coupons(db)

    return render_template(
        "admin/reports.html",
        report=report_data,
        stats=stats,
        products=products,
        coupons=coupons,
    )


@admin_bp.route("/pos", methods=["GET"])
@admin_required
def pos_terminal():
    db = get_supabase()
    products, coupons = _get_products_and_coupons(db)

    return render_template(
        "admin/pos.html",
        products=products,
        coupons=coupons,
    )


@admin_bp.route("/reports/pos-order", methods=["POST"])
@admin_required
def create_pos_order():
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    variant_id = data.get("variant_id", "").strip()
    quantity = int(data.get("quantity", 1))
    discount = float(data.get("discount", 0))
    revenue = float(data.get("revenue", 0))

    if not variant_id:
        return jsonify({"success": False, "message": "Lỗi: Vui lòng chọn màu sắc và kích thước cụ thể."}), 400
    if quantity < 1:
        return jsonify({"success": False, "message": "Số lượng phải lớn hơn 0."}), 400
    if revenue < 0 or discount < 0:
        return jsonify({"success": False, "message": "Số tiền không hợp lệ."}), 400

    try:
        db = get_supabase()

        variant_res = (
            db.table("product_variants")
            .select("id, product_id, size, color_name, stock, price_override, products(name, price)")
            .eq("id", variant_id)
            .limit(1)
            .execute()
        )
        if not variant_res.data:
            return jsonify({"success": False, "message": "Biến thể sản phẩm không tồn tại hoặc đã bị xóa."}), 404

        variant = variant_res.data[0]
        db_product_id = variant["product_id"]
        product_info = variant.get("products") or {}

        # Lấy thông tin Snapshot
        product_name = product_info.get("name", "Sản phẩm GUA")
        color_label = variant.get("color_name", "")
        size_label = variant.get("size", "")
        variant_label = f"{color_label} - Size {size_label}".strip(" -")
        
        base_price = float(product_info.get("price") or 0)
        original_price = float(variant.get("price_override") or base_price)
        variant_stock = int(variant.get("stock") or 0)

        expected_revenue = max(0, (original_price * quantity) - discount)
        if abs(revenue - expected_revenue) > 1000:
            revenue = expected_revenue

        if variant_stock < quantity:
            return jsonify({
                "success": False,
                "message": f"Không đủ hàng! Phân loại '{variant_label}' chỉ còn {variant_stock} chiếc."
            }), 400

        order_id = str(uuid.uuid4())
        order_code = f"POS-{order_id.split('-')[0].upper()}"

        db.table("orders").insert({
            "id": order_id,
            "total_amount": revenue,
            "shipping_fee": 0,
            "sales_channel": "pos",
            "status": "completed",
            "payment_status": "paid",
            "payment_method": "CASH",
        }).execute()

        # ── 5. TẠO CHI TIẾT ĐƠN VỚI SNAPSHOT DỮ LIỆU ────────────────────────
        db.table("order_items").insert({
            "order_id": order_id,
            "product_id": db_product_id,
            "variant_id": variant_id,
            "size": size_label,
            "quantity": quantity,
            "unit_price": original_price,
            "product_name": product_name,  # Snapshot tên SP
            "variant_label": variant_label  # Snapshot phân loại
        }).execute()

        # ── 6. ĐỒNG BỘ TRỪ TỒN KHO ──────────────────────────────────────────
        new_variant_stock = variant_stock - quantity
        db.table("product_variants").update({"stock": new_variant_stock}).eq("id", variant_id).execute()

        siblings_res = db.table("product_variants").select("stock").eq("product_id", db_product_id).execute()
        total_product_stock = sum(int(v.get("stock") or 0) for v in (siblings_res.data or []))
        db.table("products").update({"stock": total_product_stock}).eq("id", db_product_id).execute()

        # ── 6.5. GHI LOG LỊCH SỬ KHO (INVENTORY LOGS) ───────────────────────
        try:
            db.table("inventory_logs").insert({
                "product_id": db_product_id,
                "variant_id": variant_id,
                "change_type": "SALE",
                "quantity_changed":-quantity,
                "stock_after": new_variant_stock,
                "reference_id": order_id,
                "note": f"Bán tại quầy (POS) - {order_code}",
                "created_by": str(session.get("user_id")) if session.get("user_id") else None
            }).execute()
        except Exception as e:
            logger.error(f"[Inventory Log] Lỗi ghi log POS: {e}")

        # ── 7. CẬP NHẬT EVENT TRACKING CHO AI ───────────────────────────────
        try:
            db.rpc("log_product_event", {
                "p_product_id": db_product_id,
                "p_channel": "pos",
                "p_source": "direct",
                "p_event_type": "sold",
                "p_revenue": revenue,
                "p_qty": quantity,
            }).execute()
        except Exception as e:
            logger.error(f"[POS Analytics] Lỗi gọi RPC log_product_event: {e}")

        return jsonify({
            "success": True,
            "new_variant_stock": new_variant_stock,
            "invoice": {
                "order_code": order_code,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "product_name": f"{product_name} ({variant_label})",
                "original_price": original_price,
                "quantity": quantity,
                "discount": discount,
                "total": revenue,
            },
        })

    except Exception as e:
        logger.exception(f"[POS Error] Lỗi hệ thống khi tạo đơn POS: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống máy chủ. Vui lòng thử lại sau."}), 500

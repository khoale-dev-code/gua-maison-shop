"""
app/controllers/analytics_controller.py
Production-ready Event Tracking System (Omnichannel & AI Scoring Ready)
"""

from flask import Blueprint, request, jsonify
import logging
from app.utils.supabase_client import get_supabase
from app import csrf

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")
logger = logging.getLogger(__name__)

# ── CONFIGURATION ──────────────────────────────────────
# Whitelist chống dữ liệu bẩn
VALID_EVENTS = {"view", "cart", "wishlist", "sold"}
VALID_CHANNELS = {"web", "pos", "tiktok", "shopee", "facebook", "instagram"}


@analytics_bp.route("/track", methods=["POST"])
@csrf.exempt  # Cho phép các request fetch/sendBeacon từ UI không bị chặn CSRF
def track_event():
    try:
        # Lấy dữ liệu JSON từ request
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "Empty payload"}), 400

        # ── EXTRACT & SANITIZE DATA ────────────────────
        # 1. Định danh sản phẩm (Bắt buộc)
        product_id = data.get("product_id")
        if not product_id:
            return jsonify({"success": False, "error": "Missing product_id"}), 400

        # 2. Loại sự kiện (Validate theo whitelist)
        event_type = data.get("event_type")
        if event_type not in VALID_EVENTS:
            return jsonify({"success": False, "error": "Invalid event_type"}), 400

        # 3. Kênh & Nguồn (Mặc định: web / organic)
        channel = data.get("channel", "web")
        if channel not in VALID_CHANNELS:
            channel = "web"
            
        source = data.get("source", "organic")

        # 4. Số lượng & Doanh thu (Ép kiểu an toàn)
        try:
            qty = int(data.get("qty", 1))
            # 👉 CẬP NHẬT THEO LEADER: Thu thập doanh thu cho các event 'sold'
            revenue = float(data.get("revenue", 0)) 
        except (ValueError, TypeError):
            qty = 1
            revenue = 0

        # ── ANTI-SPAM LOGIC ────────────────────────────
        # Chặn trường hợp gửi qty quá lớn làm sai lệch báo cáo[cite: 4]
        if event_type == "view" and qty > 1:
            qty = 1
        if qty <= 0:
            qty = 1

        # ── CALL SUPABASE RPC (DATABASE LOGIC) ─────────
        db = get_supabase()

        # Gọi hàm RPC log_product_event (Cần khớp 100% với unique constraint trong DB)[cite: 4]
        res = db.rpc('log_product_event', {
            'p_product_id': product_id,
            'p_channel': channel,
            'p_source': source,
            'p_event_type': event_type,
            'p_revenue': revenue,  # Đã có doanh thu thực tế từ đơn hàng
            'p_qty': qty
        }).execute()

        # ── LOGGING & RESPONSE ─────────────────────────
        # Chỉ log info để tránh làm đầy file log, dùng error khi có sự cố thực sự[cite: 4]
        logger.info(f"[Analytics] {event_type.upper()} | {product_id} | {channel} | {source} | Qty: {qty}")

        return jsonify({"success": True})

    except Exception as e:
        # Ghi log chi tiết lỗi để Admin dễ dàng debug[cite: 4]
        logger.error(f"[Analytics CRITICAL ERROR] {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal analytics engine error"}), 500

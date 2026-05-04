"""
app/controllers/admin/admin_shipping_controller.py
Quản lý giao diện Tester và các công cụ Test API Vận chuyển độc lập.
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from app.middleware.auth_required import admin_required
from app.services.shipping_service import ShippingService
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Khởi tạo Blueprint (Nếu bạn đặt trong folder admin thì nó vẫn hoạt động tốt)
admin_shipping_bp = Blueprint("admin_shipping", __name__, url_prefix="/admin/shipping")

# ═══════════════════════════════════════════════════════════════
#  GIAO DIỆN TESTER (DÀNH CHO ADMIN / DEVELOPER)
# ═══════════════════════════════════════════════════════════════


@admin_shipping_bp.route("/tester")
@admin_required
def shipping_tester():
    """Giao diện test kết nối API Vận chuyển"""
    # Lấy danh sách provider thực tế từ Service để hiển thị ra UI
    try:
        providers = ShippingService.list_providers()
    except AttributeError:
        # Fallback an toàn nếu chưa code hàm list_providers()
        providers = [
            {"id": "ghn", "name": "Giao Hàng Nhanh (GHN)"},
            {"id": "ghtk", "name": "Giao Hàng Tiết Kiệm"},
            {"id": "mock", "name": "Môi trường Test (Mock)"}
        ]
        
    return render_template("admin/shipping_tester.html", providers=providers)

# ═══════════════════════════════════════════════════════════════
#  API ENDPOINTS CHO TESTER (AJAX CALLS)
# ═══════════════════════════════════════════════════════════════


@admin_shipping_bp.route("/api/test-fee", methods=["POST"])
@admin_required
def api_test_fee():
    """API giả lập tính phí vận chuyển"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get("provider", "mock").strip()
        
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu gửi lên"}), 400

        # Gọi Service tính phí (Controller không hề biết bên trong dùng Requests hay Urllib)
        result = ShippingService.calculate_fee(provider, data)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"[Shipping Tester] Lỗi tính phí với {provider}: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi gọi API hãng."}), 500


@admin_shipping_bp.route("/api/test-create", methods=["POST"])
@admin_required
def api_test_create():
    """API giả lập tạo vận đơn"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get("provider", "mock").strip()
        
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu gửi lên"}), 400

        # Gọi Service tạo đơn
        result = ShippingService.create_order(provider, data)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"[Shipping Tester] Lỗi tạo vận đơn với {provider}: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi gọi API hãng."}), 500

"""
app/controllers/admin/admin_shipping_providers_controller.py
Quản lý CRUD đơn vị vận chuyển (Shipping Providers).
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from app.middleware.auth_required import admin_required
from app.models.shipping_provider_model import ShippingProviderModel

logger = logging.getLogger(__name__)

admin_providers_bp = Blueprint("admin_providers", __name__, url_prefix="/admin/shipping/providers")

# ─────────────────────────────────────────────
#  PAGE
# ─────────────────────────────────────────────


@admin_providers_bp.route("/")
@admin_required
def index():
    """Trang danh sách & quản lý đơn vị vận chuyển."""
    providers = ShippingProviderModel.get_all()
    return render_template("admin/shipping_providers.html", providers=providers)

# ─────────────────────────────────────────────
#  REST JSON API  (gọi từ fetch / axios phía UI)
# ─────────────────────────────────────────────


@admin_providers_bp.route("/api", methods=["GET"])
@admin_required
def api_list():
    return jsonify(ShippingProviderModel.get_all())


@admin_providers_bp.route("/api", methods=["POST"])
@admin_required
def api_create():
    data = request.get_json(silent=True) or {}

    required = ("id", "name")
    missing = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return jsonify({"success": False, "message": f"Thiếu trường: {', '.join(missing)}"}), 400

    # Chuẩn hóa id: lowercase, no spaces
    data["id"] = data["id"].strip().lower().replace(" ", "_")
    data["name"] = data["name"].strip()
    data.setdefault("is_active", False)
    data.setdefault("sort_order", 0)
    data.setdefault("config", {})

    result = ShippingProviderModel.create(data)
    if result is None:  # ← FIX: check None thay vì falsy (vì {} cũng falsy)
        return jsonify({"success": False, "message": "ID đã tồn tại hoặc lỗi hệ thống."}), 409

    return jsonify({"success": True, "data": result}), 201


@admin_providers_bp.route("/api/<provider_id>", methods=["GET"])
@admin_required
def api_get(provider_id: str):
    row = ShippingProviderModel.get_by_id(provider_id)
    if row is None:  # ← FIX: check None thay vì falsy
        return jsonify({"success": False, "message": "Không tìm thấy."}), 404
    return jsonify(row)


@admin_providers_bp.route("/api/<provider_id>", methods=["PUT"])
@admin_required
def api_update(provider_id: str):
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"success": False, "message": "Không có dữ liệu."}), 400

    result = ShippingProviderModel.update(provider_id, data)
    if result is None:  # ← FIX: check None
        return jsonify({"success": False, "message": "Không tìm thấy hoặc lỗi cập nhật."}), 404

    return jsonify({"success": True, "data": result})


@admin_providers_bp.route("/api/<provider_id>", methods=["DELETE"])
@admin_required
def api_delete(provider_id: str):
    ok = ShippingProviderModel.delete(provider_id)
    if not ok:
        return jsonify({"success": False, "message": "Xóa thất bại."}), 500
    return jsonify({"success": True, "message": f"Đã xóa '{provider_id}'."})


@admin_providers_bp.route("/api/<provider_id>/toggle", methods=["PATCH"])
@admin_required
def api_toggle(provider_id: str):
    result = ShippingProviderModel.toggle_active(provider_id)
    if result is None:  # ← FIX: check None
        return jsonify({"success": False, "message": "Không tìm thấy."}), 404
    return jsonify({"success": True, "data": result})

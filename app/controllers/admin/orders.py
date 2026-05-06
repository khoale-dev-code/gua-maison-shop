"""
app/controllers/admin/orders.py

Cập nhật 2026:
  - Thêm route /confirm  → Bước 2: Xác nhận đơn (pending → confirmed)
  - Thêm route /pack     → Bước 3: Đóng gói xong (confirmed → packed)
  - Thêm route /webhook/ghn → Nhận webhook từ GHN, cập nhật timeline tự động
  - Tích hợp Auto-Paid: Tự động ghi nhận thanh toán COD khi giao thành công.
"""

import hmac
import hashlib
import logging
from datetime import datetime
from app import csrf 
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from app.models.order_model import OrderModel
from app.models.shipment_model import ShipmentModel
from app.middleware.auth_required import admin_required
from app.services.shipping_service import ShippingService

from ._blueprint import admin_bp
from ._helpers import handle_errors, _args, _form, _paginate, _total_pages

logger = logging.getLogger(__name__)

# ── Trạng thái hợp lệ để chuyển tiếp (State Machine guard) ──────
_TRANSITIONS = {
    "confirm": ("pending", "confirmed"),
    "pack": ("confirmed", "packed"),
}

# ═══════════════════════════════════════════════════════════════
#  DANH SÁCH ĐƠN HÀNG
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders")
@admin_required
@handle_errors("Lỗi tải danh sách đơn hàng.")
def orders():
    args = _args()
    page, per_page, _ = _paginate(args)
    status = args.get("status", "").strip() or None
    
    # 1. Hứng từ khóa tìm kiếm (q) từ URL
    keyword = args.get("q", "").strip() or None

    # 2. Truyền keyword vào hàm get_all của Model
    result = OrderModel.get_all(page=page, per_page=per_page, status=status, keyword=keyword)
    
    return render_template(
        "admin/order/orders.html",
        orders=result["items"],
        total=result["total"],
        page=page,
        total_pages=_total_pages(result["total"], per_page),
        current_status=status,
    )

# ═══════════════════════════════════════════════════════════════
#  CHI TIẾT ĐƠN HÀNG
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders/<order_id>")
@admin_required
def order_detail(order_id: str):
    order = OrderModel.get_by_id(order_id)
    if not order:
        flash("Đơn hàng không tồn tại.", "danger")
        return redirect(url_for("admin.orders"))

    shipment = ShipmentModel.get_by_order_id(order_id)
    if shipment:
        order["shipments"] = shipment

    # Chỉ lấy hãng đang bật (is_active=True) để hiển thị trong modal chọn vận chuyển
    providers = ShippingService.list_providers(active_only=True)

    # Lấy thông tin hiển thị (tên, icon) của hãng đang dùng cho shipment hiện tại
    provider_info = {}
    if shipment and shipment.get("provider"):
        provider_info = ShippingService.get_provider_display(shipment["provider"])

    return render_template(
        "admin/order/order_detail.html",
        order=order,
        providers=providers,
        provider_info=provider_info,
    )

# ═══════════════════════════════════════════════════════════════
#  BƯỚC 2 & 3: XÁC NHẬN VÀ ĐÓNG GÓI
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders/<order_id>/confirm", methods=["POST"])
@admin_required
def confirm_order(order_id: str):
    return _transition_order(order_id, "confirm")


@admin_bp.route("/orders/<order_id>/pack", methods=["POST"])
@admin_required
def pack_order(order_id: str):
    return _transition_order(order_id, "pack")


def _transition_order(order_id: str, action: str):
    """Máy trạng thái (State Machine) an toàn"""
    required_status, next_status = _TRANSITIONS[action]

    order = OrderModel.get_by_id(order_id)
    if not order:
        return jsonify({"success": False, "message": "Đơn hàng không tồn tại."})

    if order["status"] != required_status:
        label = {"confirm": "Xác nhận", "pack": "Đóng gói"}[action]
        return jsonify({
            "success": False,
            "message": f"Không thể {label}: đơn đang ở trạng thái '{order['status']}', cần '{required_status}'."
        })

    success = OrderModel.update_status(order_id, next_status)
    if success:
        logger.info(f"[Order {order_id[:8]}] {required_status} → {next_status}")
        return jsonify({"success": True, "new_status": next_status})

    return jsonify({"success": False, "message": "Lỗi cập nhật trạng thái. Vui lòng thử lại."})

# ═══════════════════════════════════════════════════════════════
#  BƯỚC 4: TẠO VẬN ĐƠN — GỌI API HÃNG VẬN CHUYỂN
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders/<order_id>/fulfill", methods=["POST"])
@admin_required
def fulfill_order(order_id: str):
    data = request.get_json(silent=True) or {}
    provider = data.get("provider", "mock").strip()

    # Lấy thông tin đơn hàng đầy đủ
    order = OrderModel.get_by_id(order_id)
    if not order:
        return jsonify({"success": False, "message": "Đơn hàng không tồn tại."})

    # Guard: Đơn hàng phải ở trạng thái packed mới được bắn sang hãng vận chuyển
    if order["status"] != "packed":
        return jsonify({
            "success": False,
            "message": f"Yêu cầu 'Đã đóng gói' để tạo vận đơn. Hiện tại: '{order['status']}'."
        })

    # 1. Khởi tạo bản ghi Shipment (Trạng thái ban đầu: pending)
    shipment_data = _build_shipment_data(order_id, order, provider)
    shipment = ShipmentModel.create_shipment(shipment_data)
    if not shipment:
        return jsonify({"success": False, "message": "Lỗi khởi tạo dữ liệu vận chuyển nội bộ."})

    # 2. Gọi API hãng vận chuyển (GHN, GHTK, v.v.)
    payload = _build_shipping_payload(shipment_data)
    api_result = ShippingService.create_order(provider, payload, shipment_db_id=shipment["id"])

    if api_result.get("success"):
        # 3. Cập nhật thông tin phản hồi từ API vào bảng shipments
        # Bao gồm: tracking_code, actual_shipping_fee, expected_delivery_at
        update_data = {
            "tracking_code": api_result.get("tracking_code"),
            "actual_shipping_fee": float(api_result.get("fee", 0)),  # Đối soát lời lỗ
            "status": "waiting_pickup",  # Chuyển sang trạng thái chờ lấy hàng[cite: 6]
            "raw_response": api_result.get("raw_response", {}),
            "shipped_at": datetime.now().isoformat()
        }
        
        # Lưu SLA nếu hãng có trả về thời gian dự kiến
        if api_result.get("expected_delivery"):
            update_data["expected_delivery_at"] = api_result.get("expected_delivery")

        # Cập nhật bảng Shipments
        from app.utils.supabase_client import get_supabase
        get_supabase().table("shipments").update(update_data).eq("id", shipment["id"]).execute()

        # 4. Ghi nhận sự kiện vào Timeline[cite: 6]
        ShipmentModel.log_event(
            shipment_id=shipment["id"],
            status="waiting_pickup",
            description=f"Đã tạo vận đơn thành công qua {provider.upper()}. Đang chờ bưu tá lấy hàng.",
            raw_data=api_result.get("raw_response", {})
        )

        # 5. Đổi trạng thái đơn hàng chính sang 'shipped' để khách hàng nhận được thông báo
        OrderModel.update_status(order_id, "shipped")
        
        logger.info(f"[Order {order_id[:8]}] Fulfill thành công | Tracking: {api_result.get('tracking_code')}")
        
        return jsonify({
            "success": True,
            "message": f"Bắn đơn sang {provider.upper()} thành công.",
            "tracking_code": api_result.get("tracking_code"),
            "actual_fee": api_result.get("fee")
        })

    # Trường hợp thất bại: Ghi log lỗi vào Timeline[cite: 6]
    error_desc = api_result.get("message", "Unknown API Error")
    ShipmentModel.log_event(
        shipment_id=shipment["id"],
        status="failed",
        description=f"Lỗi API {provider.upper()}: {error_desc}",
        raw_data=api_result.get("raw_response", {})
    )
    
    return jsonify({"success": False, "message": f"Lỗi từ {provider.upper()}: {error_desc}"})
# ═══════════════════════════════════════════════════════════════
#  WEBHOOK: GHN BẮN VỀ ĐỂ CẬP NHẬT TIMELINE (LIVE TRACKING)
# ═══════════════════════════════════════════════════════════════


# LƯU Ý: Tuyệt đối không thêm @admin_required ở đây vì Server GHN gọi vào
@admin_bp.route("/webhook/ghn", methods=["POST"])
@csrf.exempt  # <--- THỨ TỰ ĐÚNG: Nằm ngay dưới route
# (Tuyệt đối KHÔNG có @admin_required ở đây)
def webhook_ghn():
    # 1. Verify chữ ký (bỏ qua nếu chưa config SECRET)
    secret = current_app.config.get("GHN_WEBHOOK_SECRET", "")
    if secret:
        received_checksum = request.headers.get("X-Checksum", "")
        expected = hmac.new(secret.encode(), request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received_checksum, expected):
            logger.warning("[Webhook GHN] Chữ ký không hợp lệ, bỏ qua.")
            return jsonify({"message": "Invalid signature"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"message": "Empty payload"}), 400

    tracking_code = payload.get("OrderCode", "")
    ghn_status = payload.get("Status", "")
    description = payload.get("Description", ghn_status)
    location = payload.get("Warehouse", "")

    if not tracking_code or not ghn_status:
        return jsonify({"message": "Missing OrderCode or Status"}), 400

    # 2. Map status GHN → status nội bộ
    internal_status = _map_ghn_status(ghn_status)

    # 3. Tìm shipment an toàn
    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()
        res = db.table("shipments").select("id, order_id, cod_amount").eq("tracking_code", tracking_code).execute()
        if not res.data:
            return jsonify({"message": "Shipment not found"}), 404
        shipment = res.data[0]
    except Exception as e:
        logger.error(f"[Webhook GHN] Lỗi DB khi tìm tracking_code={tracking_code}: {e}")
        return jsonify({"message": "Database error"}), 500

    # 4. Ghi event vào timeline
    ShipmentModel.log_event(
        shipment_id=shipment["id"],
        status=internal_status,
        description=description,
        location=location,
        raw_data=payload,
    )

    order_id = shipment["order_id"]

    # 5. XỬ LÝ KẾT QUẢ GIAO HÀNG
    if internal_status == "delivered":
        OrderModel.update_status(order_id, "completed")
        logger.info(f"[Webhook GHN] Order {order_id[:8]} → completed")
        
        # Nếu đơn có thu hộ COD -> Tự động đánh dấu đã thanh toán
        if shipment.get("cod_amount", 0) > 0:
            OrderModel.update_payment_status(order_id, "paid", f"COD_{tracking_code}")
            logger.info(f"[Webhook GHN] Order {order_id[:8]} → auto paid via COD")

    elif internal_status in ("failed", "returned"):
        logger.warning(f"[Webhook GHN] Giao thất bại! tracking={tracking_code}")
        OrderModel.update_status(order_id, internal_status)

    return jsonify({"message": "OK"}), 200


def _map_ghn_status(ghn_status: str) -> str:
    mapping = {
        "picking": "shipping", "picked": "shipping", "storing": "shipping",
        "transporting": "shipping", "sorting": "shipping", "delivering": "shipping",
        "money_collect_delivering": "shipping",
        "delivered": "delivered",
        "delivery_fail": "failed",
        "waiting_to_return":"returned", "return": "returned", "returned": "returned",
        "cancel": "cancelled",
    }
    return mapping.get(ghn_status.lower(), "shipping")

# ═══════════════════════════════════════════════════════════════
#  BƯỚC 5 (SELF_SHIP): XÁC NHẬN GIAO THÀNH CÔNG THỦ CÔNG
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders/<order_id>/self-delivered", methods=["POST"])
@admin_required
def self_delivered(order_id: str):
    """
    Self Ship: Admin xác nhận giao tay thành công.
    Guard: status == 'shipped' AND provider == 'self_ship'
    """
    order = OrderModel.get_by_id(order_id)
    if not order:
        return jsonify({"success": False, "message": "Đơn hàng không tồn tại."})

    if order["status"] != "shipped":
        return jsonify({"success": False, "message": f"Đơn phải ở trạng thái 'shipped'. Hiện: '{order['status']}'."})

    shipment = ShipmentModel.get_by_order_id(order_id)
    if not shipment or shipment.get("provider") != "self_ship":
        return jsonify({"success": False, "message": "Chỉ áp dụng cho đơn tự giao (Self Ship)."})

    tracking_code = shipment.get("tracking_code", "")
    ShipmentModel.log_event(
        shipment_id=shipment["id"],
        status="delivered",
        description=f"Admin xác nhận giao thành công. Mã: {tracking_code}.",
    )
    OrderModel.update_status(order_id, "completed")
    logger.info(f"[Order {order_id[:8]}] shipped → completed (self_ship)")

    is_cod = order.get("payment_method", "").upper() in ("COD", "TIỀN MẶT", "CASH")
    if is_cod and order.get("payment_status") != "paid":
        OrderModel.update_payment_status(order_id, "paid", f"SELFSHIP_COD_{tracking_code}")
        logger.info(f"[Order {order_id[:8]}] auto paid via self_ship COD")

    return jsonify({"success": True})

# ═══════════════════════════════════════════════════════════════
#  CẬP NHẬT ĐỊA CHỈ & THANH TOÁN
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders/<order_id>/update-ship-fee", methods=["POST"])
@admin_required
def update_ship_fee(order_id: str):
    """
    Cập nhật phí ship thực tế cho đơn self_ship.
    Payload: { shipping_fee: float, sub_method: str, add_to_total: bool }

    sub_method: 'staff' | 'grab' | 'bee' | 'ahamove'
    add_to_total: nếu True → cộng shipping_fee vào orders.total_amount
    """
    order = OrderModel.get_by_id(order_id)
    if not order:
        return jsonify({"success": False, "message": "Đơn hàng không tồn tại."})

    shipment = ShipmentModel.get_by_order_id(order_id)
    if not shipment or shipment.get("provider") != "self_ship":
        return jsonify({"success": False, "message": "Chỉ áp dụng cho đơn tự giao."})

    data = request.get_json(silent=True) or {}
    fee = float(data.get("shipping_fee", 0))
    sub_method = data.get("sub_method", "staff").strip()
    add_flag = bool(data.get("add_to_total", False))

    try:
        from app.utils.supabase_client import get_supabase
        db = get_supabase()

        # Ghi shipping_fee + sub_method vào shipments
        db.table("shipments").update({
            "shipping_fee": fee,
            "raw_response": {
                **(shipment.get("raw_response") or {}),
                "sub_method": sub_method,
            }
        }).eq("id", shipment["id"]).execute()

        # Cộng vào total_amount nếu admin chọn
        if add_flag and fee > 0:
            new_total = float(order["total_amount"]) + fee
            db.table("orders").update({"total_amount": new_total}).eq("id", order_id).execute()
            logger.info(f"[Order {order_id[:8]}] total_amount +{fee} → {new_total} (ship fee added)")

        ShipmentModel.log_event(
            shipment_id=shipment["id"],
            status=shipment.get("status", "shipped"),
            description=(
                f"Cập nhật phí ship: {fee:,.0f}₫ "
                f"| {sub_method}"
                f"{' | Đã cộng vào tổng đơn' if add_flag and fee > 0 else ''}"
            ),
        )
        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"[Order {order_id[:8]}] update_ship_fee error: {e}")
        return jsonify({"success": False, "message": "Lỗi cập nhật. Vui lòng thử lại."})


@admin_required
@handle_errors("Cập nhật địa chỉ thất bại.", "admin.orders")
def edit_order_address(order_id):
    form = _form()
    address = {k: form.get(k) for k in ("full_name", "phone", "address", "city", "district")}
    if OrderModel.update_shipping_address(order_id, address):
        flash("Đã cập nhật địa chỉ giao hàng!", "success")
    else:
        flash("Cập nhật địa chỉ thất bại.", "danger")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/orders/<order_id>/payment-status", methods=["POST"])
@admin_required
@handle_errors("Lỗi hệ thống.", "admin.orders")
def update_payment_status(order_id: str):
    new_status = _form().get("payment_status")
    txn_id = f"MANUAL_ADMIN_{datetime.now().strftime('%H%M%S')}" if new_status == "paid" else None
    
    if OrderModel.update_payment_status(order_id, payment_status=new_status, transaction_id=txn_id):
        flash("Đã xác nhận thu tiền thành công!", "success")
    else:
        flash("Cập nhật thanh toán thất bại.", "danger")
    return redirect(url_for("admin.order_detail", order_id=order_id))

# ═══════════════════════════════════════════════════════════════
#  PRIVATE BUILDERS
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
#  PRIVATE BUILDERS
# ═══════════════════════════════════════════════════════════════


def _build_shipment_data(order_id: str, order: dict, provider: str) -> dict:
    addr = order.get("shipping_address", {})
    items = order.get("order_items", [])
    
    # Giả định khối lượng: 250g/sản phẩm thời trang
    total_weight = sum(item.get("quantity", 1) * 250 for item in items)
    weight_g = max(total_weight, 500)  # Tối thiểu 500g

    # 👉 GHÉP CHUỖI ĐỊA CHỈ ĐẦY ĐỦ TRƯỚC KHI LƯU VÀO DB
    address_parts = [
        addr.get("address", ""),
        addr.get("district", ""),
        addr.get("city", "")
    ]
    full_address = ", ".join([part for part in address_parts if part])

    return {
        "order_id": order_id,
        "provider": provider,
        "recipient_name": addr.get("full_name", ""),
        "recipient_phone": addr.get("phone", ""),
        "recipient_address": full_address,  # Lưu địa chỉ đã được ghép đầy đủ
        "recipient_ward_code": addr.get("ward_code", ""),
        "recipient_district_id": addr.get("district_id"),
        "recipient_province_id": addr.get("province_id"),
        "cod_amount": float(order["total_amount"]) if order.get("payment_method") == "COD" else 0,
        "shipping_fee": float(order.get("shipping_fee", 0)),  # Phí đã thu của khách
        "weight_g": weight_g,
        "dimensions_json": {"l": 20, "w": 15, "h": 10},  # Kích thước hộp tiêu chuẩn
        "status": "pending",
        "package_index": 1  # Mặc định kiện số 1
    }


def _build_shipping_payload(sd: dict) -> dict:
    # Ở bước này chỉ cần lấy ra và bắn thẳng sang API (GHN/GHTK)
    return {
        "to_name": sd.get("recipient_name", ""),
        "to_phone": sd.get("recipient_phone", ""),
        "to_address": sd.get("recipient_address", ""),  # Đã có sẵn Quận/Huyện, Tỉnh/Thành
        "cod_amount": sd.get("cod_amount", 0),
        "weight": sd.get("weight_g", 500),
    }

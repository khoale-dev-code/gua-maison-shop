"""
app/models/order_model.py
Quản lý vòng đời đơn hàng, thống kê tài chính, logistics và hỗ trợ vận hành.

Cập nhật 2026:
  - request_return()  → ghi vào bảng return_requests (tách riêng)
  - approve_return()  → admin duyệt yêu cầu đổi/trả
  - complete_refund() → admin xác nhận đã hoàn tiền → trừ doanh thu
  - get_stats()       → Tính Toán Doanh Thu + Tích hợp KPI Vận Chuyển (Logistics)
"""

import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class OrderModel:

    # ═══════════════════════════════════════════════════════════════
    #  TẠO ĐƠN HÀNG (Dành cho Checkout)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def create_order(user_id: str, items: list, total: float, address: dict,
                     payment_method: str='COD', order_notes: str=None) -> dict:
        db = get_supabase()
        try:
            order_data = {
                "user_id": user_id,
                "total_amount": float(total),
                "shipping_address": address,
                "status": "pending",
                "payment_method": payment_method.upper(),
                "payment_status": "pending",
                "order_notes": order_notes,
            }

            r = db.table("orders").insert(order_data).execute()
            if not r.data:
                return {}

            order = r.data[0]
            order_id = order["id"]

            order_items = []
            for item in items:
                prod = item.get("products", {}) if isinstance(item.get("products"), dict) else {}
                order_items.append({
                    "order_id": order_id,
                    "product_id": item.get("product_id"),
                    "variant_id": item.get("variant_id"),  # QUAN TRỌNG: Lưu liên kết với bảng biến thể
                    "quantity": int(item.get("quantity", 1)),
                    "unit_price": float(prod.get("price", 0)),
                    "size": item.get("size"),
                })

            if order_items:
                db.table("order_items").insert(order_items).execute()

            return order

        except Exception as e:
            logger.exception(f"Lỗi tạo đơn hàng: {e}")
            return {}

   # ═══════════════════════════════════════════════════════════════
    #  THỐNG KÊ DASHBOARD  (Doanh Thu & KPI Vận Chuyển)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_stats() -> dict:
        db = get_supabase()
        stats = {
            "total_orders": 0,
            "total_revenue": 0,
            "pending": 0,
            "vnpay_orders": 0,
            "vnpay_ratio": 0,
            "monthly": [],
            "status_chart": [],
            "_orders": [],
            "vnpay_recent": [],
            "pending_returns": 0,
            # KPIs Logistics
            "delivery_success": 0,
            "return_rate": 0,
            "avg_time": 0
        }

        try:
            # 1. THỐNG KÊ DOANH THU & ĐƠN HÀNG
            r = (
                db.table("orders")
                .select("id, total_amount, refunded_amount, status, payment_method, payment_status, created_at, users(full_name, email)")
                .order("created_at", desc=True)
                .limit(500)
                .execute()
            )

            orders = r.data or []
            stats["total_orders"] = len(orders)
            stats["_orders"] = orders[:8]

            status_counts = Counter()
            monthly_revenue = defaultdict(float)
            paid_orders = []
            vnpay_paid = []
            pending_count = 0

            for o in orders:
                status = o.get("status", "pending")
                amount = float(o.get("total_amount", 0))
                refunded = float(o.get("refunded_amount") or 0)
                payment_method = o.get("payment_method", "").upper()
                payment_status = o.get("payment_status", "pending")

                status_counts[status] += 1

                # Doanh thu thực = amount đã thu - phần đã hoàn lại
                if payment_status == "paid":
                    net_revenue = amount - refunded
                    stats["total_revenue"] += net_revenue
                    paid_orders.append(o)

                    if payment_method == "VNPAY":
                        vnpay_paid.append(o)

                    if o.get("created_at"):
                        month = o["created_at"][:7]
                        monthly_revenue[month] += net_revenue

                if status == "pending" and (payment_method == "COD" or payment_status == "paid"):
                    pending_count += 1

            stats["pending"] = pending_count
            stats["vnpay_orders"] = len(vnpay_paid)
            if paid_orders:
                stats["vnpay_ratio"] = round((len(vnpay_paid) / len(paid_orders)) * 100, 1)

            stats["vnpay_recent"] = sorted(vnpay_paid, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
            stats["status_chart"] = [{"status": k, "count": v} for k, v in status_counts.items()]
            stats["monthly"] = [{"month": k, "revenue": round(v)} for k, v in sorted(monthly_revenue.items())[-6:]]

            # 2. THỐNG KÊ ĐỔI TRẢ
            try:
                rr = db.table("return_requests").select("id", count="exact").eq("status", "pending").execute()
                stats["pending_returns"] = rr.count or 0
            except Exception:
                pass

            # 3. THỐNG KÊ VẬN CHUYỂN (LOGISTICS)
            shipments_res = db.table("shipments").select("status, created_at, shipped_at, delivered_at").execute()
            shipments = shipments_res.data or []
            
            total_shipped = len(shipments)
            delivered_count = sum(1 for s in shipments if s["status"] == "delivered")
            returned_count = sum(1 for s in shipments if s["status"] in ("returned", "failed", "cancelled"))
            
            stats["delivery_success"] = round((delivered_count / total_shipped * 100), 1) if total_shipped > 0 else 0
            stats["return_rate"] = round((returned_count / total_shipped * 100), 1) if total_shipped > 0 else 0
            
            total_days = 0
            valid_deliveries = 0
            for s in shipments:
                if s["status"] == "delivered" and s.get("shipped_at") and s.get("delivered_at"):
                    try:
                        start = datetime.fromisoformat(s["shipped_at"].replace('Z', '+00:00'))
                        end = datetime.fromisoformat(s["delivered_at"].replace('Z', '+00:00'))
                        
                        # Thay đổi: Dùng total_seconds để lấy số ngày chính xác (vd: 1.5 ngày)
                        total_days += (end - start).total_seconds() / 86400.0
                        valid_deliveries += 1
                    except Exception: 
                        pass
                    
            stats["avg_time"] = round((total_days / valid_deliveries), 1) if valid_deliveries > 0 else 0

        except Exception as e:
            logger.exception(f"Lỗi lấy thống kê Dashboard: {e}")

        return stats
    # ═══════════════════════════════════════════════════════════════
    #  QUẢN LÝ ĐƠN HÀNG (CHI TIẾT & DANH SÁCH)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_by_id(order_id: str):
        """Lấy chi tiết 1 đơn hàng đầy đủ item, ảnh, CHUẨN BIẾN THỂ và return_request."""
        db = get_supabase()
        try:
            r = (
                db.table("orders")
                # ĐÃ FIX: Lấy chuẩn xác product_variants(*) để giao diện hiển thị size/màu
                .select("*, users(full_name, email, phone), order_items(*, products(id, name, thumbnail_url, slug), product_variants(*))")
                .eq("id", order_id)
                .single()
                .execute()
            )
            order = r.data
            if not order:
                return None

            try:
                rr = (
                    db.table("return_requests")
                    .select("*")
                    .eq("order_id", order_id)
                    .order("requested_at", desc=True)
                    .limit(1)
                    .execute()
                )
                order["return_request"] = rr.data[0] if rr.data else None
            except Exception:
                order["return_request"] = None

            return order
        except Exception as e:
            logger.error(f"Lỗi get_by_id cho đơn {order_id}: {e}")
            return None

    @staticmethod
    def get_all(page: int=1, per_page: int=20, status: str=None):
        db = get_supabase()
        offset = (page - 1) * per_page
        try:
            query = (
                db.table("orders")
                .select("*, users(email, full_name, phone), order_items(*, products(id, name, thumbnail_url))", count="exact")
                .order("created_at", desc=True)
            )
            if status:
                query = query.eq("status", status)

            r = query.range(offset, offset + per_page - 1).execute()
            return {"items": r.data or [], "total": r.count or 0}
        except Exception as e:
            logger.error(f"Lỗi lấy danh sách đơn hàng: {e}")
            return {"items": [], "total": 0}

    @staticmethod
    def get_user_orders(user_id: str):
        db = get_supabase()
        try:
            r = (
                db.table("orders")
                # ĐÃ FIX: Lấy thêm order_items, products và product_variants
                .select("*, order_items(*, products(id, name, thumbnail_url, slug), product_variants(*))")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return r.data or []
        except Exception as e:
            logger.error(f"Lỗi lấy đơn hàng user {user_id}: {e}")
            return []

    @staticmethod
    def get_user_orders_paginated(user_id: str, page: int=1, per_page: int=10) -> dict:
        db = get_supabase()
        offset = (page - 1) * per_page
        try:
            r = (
                db.table("orders")
                # ĐÃ FIX: Lấy thêm order_items, products và product_variants để hiển thị ảnh, size, màu
                .select("*, order_items(*, products(id, name, thumbnail_url, slug), product_variants(*))", count="exact")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + per_page - 1)
                .execute()
            )
            total = r.count or 0
            total_pages = max(1, -(-total // per_page))
            return {
                "items": r.data or [],
                "pagination": {
                    "page": page, "per_page": per_page, "total": total, "total_pages": total_pages,
                    "has_prev": page > 1, "has_next": page < total_pages,
                },
            }
        except Exception as e:
            logger.error(f"Lỗi lấy đơn hàng phân trang user {user_id}: {e}")
            return {"items": [], "pagination": {"page": 1, "per_page": per_page, "total": 0, "total_pages": 1, "has_prev": False, "has_next": False}}
    # ═══════════════════════════════════════════════════════════════
    #  CẬP NHẬT TRẠNG THÁI & HOTLINE
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def update_status(order_id: str, status: str) -> bool:
        db = get_supabase()
        try:
            db.table("orders").update({"status": status}).eq("id", order_id).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi cập nhật trạng thái đơn {order_id}: {e}")
            return False

    @staticmethod
    def update_payment_status(order_id: str, payment_status: str, transaction_id: str=None) -> bool:
        db = get_supabase()
        try:
            payload = {"payment_status": payment_status}
            if transaction_id:
                payload["transaction_id"] = transaction_id
            db.table("orders").update(payload).eq("id", order_id).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi cập nhật thanh toán đơn {order_id}: {e}")
            return False

    @staticmethod
    def update_shipping_address(order_id: str, new_address: dict) -> bool:
        db = get_supabase()
        try:
            db.table("orders").update({"shipping_address": new_address}).eq("id", order_id).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi sửa địa chỉ Hotline cho đơn {order_id}: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  HỦY ĐƠN & ĐỔI TRẢ — KHÁCH HÀNG & ADMIN
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def cancel_order_by_user(order_id: str, user_id: str) -> tuple[bool, str]:
        db = get_supabase()
        try:
            order_res = db.table("orders").select("created_at, status").eq("id", order_id).eq("user_id", user_id).single().execute()
            if not order_res.data:
                return False, "Không tìm thấy đơn hàng."

            order = order_res.data
            if order["status"] != "pending":
                return False, "Đơn hàng đã được xử lý, không thể tự hủy."

            created_time = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
            hours_passed = (datetime.now(timezone.utc) - created_time).total_seconds() / 3600

            if hours_passed > 3:
                return False, "Đã quá 3 giờ kể từ lúc đặt. Vui lòng liên hệ Hotline để hủy."

            db.table("orders").update({"status": "cancelled"}).eq("id", order_id).execute()
            return True, "Đã hủy đơn hàng thành công."
        except Exception as e:
            logger.error(f"Lỗi hủy đơn user: {e}")
            return False, "Lỗi hệ thống."

    @staticmethod
    def request_return(order_id: str, user_id: str, reason: str, image_url: str) -> tuple[bool, str]:
        db = get_supabase()
        try:
            order_res = db.table("orders").select("status, is_return_requested").eq("id", order_id).eq("user_id", user_id).single().execute()
            if not order_res.data:
                return False, "Không tìm thấy đơn hàng."

            order = order_res.data
            if order["status"] != "delivered":
                return False, "Chỉ đơn hàng đã giao mới được yêu cầu đổi/trả."

            existing = db.table("return_requests").select("id, status").eq("order_id", order_id).in_("status", ["pending", "approved", "refunded"]).execute()
            if existing.data:
                return False, "Bạn đã có yêu cầu đổi/trả đang được xử lý cho đơn này."

            db.table("return_requests").insert({
                "order_id": order_id, "user_id": user_id, "reason": reason, "image_url": image_url, "status": "pending",
            }).execute()

            db.table("orders").update({
                "is_return_requested": True, "return_reason": reason, "return_image_url": image_url,
            }).eq("id", order_id).execute()

            return True, "Yêu cầu đổi/trả đã được ghi nhận. Đội ngũ GUA sẽ liên hệ bạn trong 24 giờ."
        except Exception as e:
            logger.error(f"Lỗi gửi yêu cầu đổi/trả: {e}")
            return False, "Lỗi hệ thống."

    @staticmethod
    def get_return_requests(page: int=1, per_page: int=20, status: str=None) -> dict:
        db = get_supabase()
        offset = (page - 1) * per_page
        try:
            query = (
                db.table("return_requests")
                .select("*, orders(id, total_amount, payment_status, payment_method, refunded_amount), users(full_name, email, phone)", count="exact")
                .order("requested_at", desc=True)
            )
            if status: query = query.eq("status", status)

            r = query.range(offset, offset + per_page - 1).execute()
            return {"items": r.data or [], "total": r.count or 0}
        except Exception as e:
            logger.error(f"Lỗi lấy return_requests: {e}")
            return {"items": [], "total": 0}

    @staticmethod
    def get_return_request_by_id(rr_id: str) -> dict | None:
        db = get_supabase()
        try:
            r = db.table("return_requests").select("*, orders(*, order_items(*, products(name, thumbnail_url))), users(full_name, email, phone)").eq("id", rr_id).single().execute()
            return r.data
        except Exception:
            return None

    @staticmethod
    def approve_return(rr_id: str, admin_user_id: str, admin_note: str="") -> tuple[bool, str]:
        db = get_supabase()
        try:
            rr = db.table("return_requests").select("status").eq("id", rr_id).single().execute().data
            if not rr: return False, "Yêu cầu không tồn tại."
            if rr["status"] != "pending": return False, f"Yêu cầu đang ở trạng thái '{rr['status']}', không thể duyệt."

            db.table("return_requests").update({
                "status": "approved", "reviewed_by": admin_user_id, "reviewed_at": datetime.now(timezone.utc).isoformat(), "admin_note": admin_note.strip() or None,
            }).eq("id", rr_id).execute()

            return True, "Đã duyệt yêu cầu đổi/trả. Tiến hành liên hệ khách hàng để nhận lại hàng."
        except Exception as e:
            logger.error(f"Lỗi duyệt return_request {rr_id}: {e}")
            return False, "Lỗi hệ thống."

    @staticmethod
    def reject_return(rr_id: str, admin_user_id: str, admin_note: str) -> tuple[bool, str]:
        db = get_supabase()
        try:
            if not admin_note or not admin_note.strip(): return False, "Vui lòng nhập lý do từ chối."

            rr = db.table("return_requests").select("status, order_id").eq("id", rr_id).single().execute().data
            if not rr: return False, "Yêu cầu không tồn tại."
            if rr["status"] != "pending": return False, f"Yêu cầu đang ở trạng thái '{rr['status']}', không thể từ chối."

            db.table("return_requests").update({
                "status": "rejected", "reviewed_by": admin_user_id, "reviewed_at": datetime.now(timezone.utc).isoformat(), "admin_note": admin_note.strip(),
            }).eq("id", rr_id).execute()

            db.table("orders").update({"is_return_requested": False}).eq("id", rr["order_id"]).execute()
            return True, "Đã từ chối yêu cầu. Khách hàng có thể gửi lại nếu muốn."
        except Exception as e:
            logger.error(f"Lỗi từ chối return_request {rr_id}: {e}")
            return False, "Lỗi hệ thống."

    @staticmethod
    def complete_refund(rr_id: str, admin_user_id: str, refund_amount: float=None) -> tuple[bool, str]:
        db = get_supabase()
        try:
            rr = db.table("return_requests").select("status, order_id").eq("id", rr_id).single().execute().data
            if not rr: return False, "Yêu cầu không tồn tại."
            if rr["status"] != "approved": return False, "Yêu cầu phải ở trạng thái 'Đã duyệt' trước khi xác nhận hoàn tiền."

            order_id = rr["order_id"]
            order = db.table("orders").select("total_amount, refunded_amount, payment_status").eq("id", order_id).single().execute().data
            if not order: return False, "Không tìm thấy đơn hàng liên quan."

            total_amount = float(order["total_amount"])
            already_refunded = float(order.get("refunded_amount") or 0)
            max_refundable = total_amount - already_refunded

            amount_to_refund = float(refund_amount) if refund_amount else total_amount
            amount_to_refund = min(amount_to_refund, max_refundable)

            if amount_to_refund <= 0: return False, "Đơn hàng này đã được hoàn tiền đầy đủ trước đó."

            now_iso = datetime.now(timezone.utc).isoformat()
            db.table("return_requests").update({
                "status": "refunded", "refunded_at": now_iso, "refund_amount": amount_to_refund, "reviewed_by": admin_user_id,
            }).eq("id", rr_id).execute()

            db.table("orders").update({"refunded_amount": already_refunded + amount_to_refund}).eq("id", order_id).execute()
            return True, f"Đã xác nhận hoàn tiền {amount_to_refund:,.0f}đ. Doanh thu đã được cập nhật."
        except Exception as e:
            logger.error(f"Lỗi xác nhận hoàn tiền return_request {rr_id}: {e}")
            return False, "Lỗi hệ thống."

    # ═══════════════════════════════════════════════════════════════
    #  THỐNG KÊ KHÁCH HÀNG
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_user_count() -> int:
        db = get_supabase()
        try:
            r = db.table("users").select("id", count="exact").eq("role", "customer").execute()
            return r.count or 0
        except Exception:
            return 0
    # ═══════════════════════════════════════════════════════════════
    #  STATE MACHINE: Chuyển trạng thái CÓ KIỂM TRA
    # ═══════════════════════════════════════════════════════════════
 
    # Luồng hợp lệ: status_hiện_tại → [status_có_thể_chuyển_sang]
    _VALID_TRANSITIONS = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["packed", "cancelled"],
        "packed": ["shipped", "cancelled"],
        "shipped": ["delivered", "failed", "returned"],
        "shipping": ["delivered", "failed", "returned"],
        "delivered": ["completed", "returned"],
        "completed": [],  # Trạng thái cuối, không chuyển thêm
        "cancelled": [],  # Trạng thái cuối
        "failed": ["returned"],
        "returned": [],
    }
 
    @staticmethod
    def update_status_guarded(order_id: str, new_status: str) -> tuple[bool, str]:
        """
        Cập nhật trạng thái đơn hàng có kiểm tra luồng hợp lệ.
        Trả về (True, "") nếu thành công, (False, "lý do") nếu không hợp lệ.
 
        Dùng trong controller khi cần bảo vệ chặt. 
        Ví dụ: không thể chuyển từ 'completed' về 'pending'.
        """
        db = get_supabase()
        try:
            order = db.table("orders").select("status").eq("id", order_id).single().execute().data
            if not order:
                return False, "Đơn hàng không tồn tại."
 
            current = order["status"]
            allowed = OrderModel._VALID_TRANSITIONS.get(current, [])
 
            if new_status not in allowed:
                return False, (
                    f"Không thể chuyển từ '{current}' sang '{new_status}'. "
                    f"Trạng thái hợp lệ tiếp theo: {allowed or ['(không có)']}"
                )
 
            db.table("orders").update({"status": new_status}).eq("id", order_id).execute()
            logger.info(f"[OrderModel] Order {order_id[:8]}: {current} → {new_status}")
            return True, ""
 
        except Exception as e:
            logger.error(f"Lỗi update_status_guarded cho đơn {order_id}: {e}")
            return False, "Lỗi hệ thống."
 
    @staticmethod
    def get_status_counts() -> dict:
        """
        Đếm số đơn theo từng trạng thái — dùng để hiện badge số trên tab.
        Trả về: {'pending': 5, 'confirmed': 2, ...}
        """
        db = get_supabase()
        try:
            rows = db.table("orders").select("status").execute().data or []
            from collections import Counter
            return dict(Counter(r["status"] for r in rows))
        except Exception as e:
            logger.error(f"Lỗi get_status_counts: {e}")
            return {}

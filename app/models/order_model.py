"""
app/models/order_model.py – Quản lý đơn hàng & Thống kê (Supabase Edition)
Tối ưu hóa cho Dashboard Admin và Microservice Analytics.
"""
import logging
from collections import defaultdict, Counter
from app.utils.supabase_client import get_supabase

# Cấu hình logging
logger = logging.getLogger(__name__)

class OrderModel:

    @staticmethod
    def create_order(user_id: str, items: list, total: float, address: dict) -> dict:
        """Tạo đơn hàng mới (Master-Detail record)."""
        db = get_supabase()
        try:
            # 1. Insert vào bảng 'orders'
            r = db.table("orders").insert({
                "user_id": user_id,
                "total_amount": total,
                "shipping_address": address,
                "status": "pending",
            }).execute()

            if not r.data:
                return {}

            order = r.data[0]
            
            # 2. Chuẩn bị dữ liệu cho 'order_items'
            order_items = []
            for item in items:
                prod_info = item.get("products", {})
                price = prod_info.get("price", 0) if isinstance(prod_info, dict) else 0
                
                order_items.append({
                    "order_id": order["id"],
                    "product_id": item["product_id"],
                    "quantity": item["quantity"],
                    "unit_price": price,
                    "size": item.get("size"),
                })

            if order_items:
                db.table("order_items").insert(order_items).execute()
            
            return order
        except Exception as e:
            logger.error(f"🔥 Lỗi tạo đơn hàng: {str(e)}")
            return {}

    @staticmethod
    def get_user_orders_paginated(user_id: str, page: int=1, per_page: int=10) -> dict:
        """Lấy lịch sử mua hàng có phân trang cho khách hàng."""
        db = get_supabase()
        offset = (page - 1) * per_page
        try:
            r = db.table("orders") \
                .select("*, order_items(*, products(name, thumbnail_url, price))", count="exact") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .range(offset, offset + per_page - 1) \
                .execute()

            total_count = r.count or 0
            return {
                "items": r.data,
                "pagination": {
                    "current_page": page,
                    "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1
                }
            }
        except Exception as e:
            logger.error(f"Lỗi phân trang đơn hàng: {e}")
            return {"items": [], "pagination": {"current_page": 1, "total_pages": 1}}

    @staticmethod
    def get_user_orders(user_id: str) -> list:
        """Lấy toàn bộ đơn hàng của 1 user (Dùng cho Dashboard Profile)."""
        db = get_supabase()
        try:
            r = db.table("orders") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
            return r.data
        except Exception as e:
            logger.error(f"Lỗi lấy đơn hàng user: {e}")
            return []

    @staticmethod
    def get_by_id(order_id: str) -> dict | None:
        """Chi tiết 1 đơn hàng (Dùng cho cả Admin và Khách)."""
        db = get_supabase()
        try:
            r = db.table("orders") \
                .select("*, order_items(*, products(name, thumbnail_url)), users(full_name, email)") \
                .eq("id", order_id) \
                .single() \
                .execute()
            return r.data
        except Exception:
            return None

    @staticmethod
    def get_all(page: int=1, per_page: int=20, status: str=None) -> dict:
        """Quản lý đơn hàng dành cho Admin."""
        db = get_supabase()
        offset = (page - 1) * per_page
        try:
            q = db.table("orders").select("*, users(email, full_name)", count="exact") \
                .order("created_at", desc=True)
            
            if status:
                q = q.eq("status", status)
                
            r = q.range(offset, offset + per_page - 1).execute()
            return {"items": r.data, "total": r.count or 0}
        except Exception as e:
            logger.error(f"Lỗi Admin Order List: {e}")
            return {"items": [], "total": 0}

    @staticmethod
    def update_status(order_id: str, status: str) -> bool:
        """Cập nhật trạng thái đơn hàng."""
        db = get_supabase()
        try:
            db.table("orders").update({"status": status}).eq("id", order_id).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def get_stats() -> dict:
        """
        Tổng hợp dữ liệu Dashboard Admin.
        Tối ưu: Chỉ lấy các field cần thiết để giảm tải RAM.
        """
        db = get_supabase()
        stats = {
            "total_orders": 0, "total_revenue": 0,
            "pending": 0, "delivered": 0, "cancelled": 0,
            "monthly": [], "status_chart": [], "_orders": []
        }
        try:
            # Lấy data thô để xử lý thống kê
            r = db.table("orders").select("status, total_amount, created_at").order("created_at", desc=True).execute()
            orders = r.data
            
            stats["total_orders"] = len(orders)
            # Chỉ lấy 5 đơn hàng mới nhất để hiển thị ở bảng Dashboard
            stats["_orders"] = orders[:5] 
            
            status_counts = Counter()
            monthly_revenue = defaultdict(float)
            
            for o in orders:
                status = o.get("status", "unknown")
                status_counts[status] += 1
                
                amount = float(o.get("total_amount", 0))
                # Không tính doanh thu cho đơn đã hủy
                if status != "cancelled":
                    stats["total_revenue"] += amount
                    if o.get("created_at"):
                        # format: YYYY-MM
                        month_key = o["created_at"][:7] 
                        monthly_revenue[month_key] += amount

            # Đóng gói dữ liệu chart
            stats.update({
                "pending": status_counts["pending"],
                "delivered": status_counts["delivered"],
                "cancelled": status_counts["cancelled"],
                "status_chart": [{"status": k, "count": v} for k, v in status_counts.items()],
                "monthly": [{"month": k, "revenue": v} for k, v in sorted(monthly_revenue.items())][-6:]
            })

        except Exception as e:
            logger.error(f"Lỗi thống kê Dashboard: {e}")
            
        return stats

    @staticmethod
    def get_user_count() -> int:
        """Đếm tổng số khách hàng."""
        db = get_supabase()
        try:
            # Chỉ đếm user có role là customer
            r = db.table("users").select("id", count="exact").eq("role", "customer").execute()
            return r.count or 0
        except Exception:
            return 0    
"""
app/models/cart_model.py
Quản lý dữ liệu Giỏ hàng của người dùng.
Phiên bản Premium: Tích hợp kiểm tra tồn kho (Stock Check), 
chống Over-sell và lọc dữ liệu mồ côi (Orphan Data).
"""

import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class CartModel:

    @staticmethod
    def _db():
        """Helper lấy kết nối Supabase"""
        return get_supabase()

    @staticmethod
    def get_user_cart(user_id: str) -> list:
        """
        Lấy toàn bộ sản phẩm trong giỏ.
        Tự động Join với products và product_variants. Có bộ lọc an toàn.
        """
        try:
            res = CartModel._db().table("cart_items") \
                .select("*, products(id, name, price, thumbnail_url, stock, slug, is_active, deleted_at), product_variants(*)") \
                .eq("user_id", user_id) \
                .order("created_at", desc=False) \
                .execute()
            
            # Lọc bỏ dữ liệu rác (Sản phẩm hoặc Biến thể đã bị Admin xóa hẳn khỏi Database)
            valid_items = []
            if res.data:
                for item in res.data:
                    # Chỉ lấy item nếu products và product_variants vẫn còn dữ liệu
                    if item.get("products") and item.get("product_variants"):
                        valid_items.append(item)
                        
            return valid_items
        except Exception as e:
            logger.error(f"Lỗi get_user_cart cho user {user_id}: {e}")
            return []

    @staticmethod
    def get_count(user_id: str) -> int:
        """Đếm tổng số lượng sản phẩm trong giỏ hàng"""
        try:
            items = CartModel.get_user_cart(user_id)
            return sum(item.get("quantity", 0) for item in items)
        except Exception as e:
            logger.error(f"Lỗi get_count: {e}")
            return 0

    @staticmethod
    def add_item(user_id: str, product_id: str, variant_id: str, quantity: int=1) -> dict:
        """
        Thêm sản phẩm vào giỏ với Logic Cực Chặt:
        1. Check xem biến thể có tồn tại không.
        2. Ép số lượng mua KHÔNG VƯỢT QUÁ tồn kho.
        """
        db = CartModel._db()
        try:
            # Bước 1: Kiểm tra Tồn kho thực tế của Biến thể
            variant_check = db.table("product_variants").select("stock").eq("id", variant_id).execute()
            if not variant_check.data:
                logger.warning(f"Thêm giỏ hàng thất bại: Variant {variant_id} không tồn tại.")
                return {}
            
            max_stock = variant_check.data[0].get("stock", 0)
            if max_stock <= 0:
                logger.warning("Thêm giỏ hàng thất bại: Hết hàng.")
                return {}  # Đã hết hàng, từ chối thêm

            # Bước 2: Kiểm tra item đã có trong giỏ chưa
            existing = db.table("cart_items") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("variant_id", variant_id) \
                .execute()
            
            if existing.data:
                # Nếu có rồi -> Cộng dồn và Ép giới hạn tồn kho
                item_id = existing.data[0]["id"]
                new_qty = existing.data[0]["quantity"] + quantity
                
                if new_qty > max_stock:
                    new_qty = max_stock  # Chống mua lố tồn kho
                    
                res = db.table("cart_items") \
                    .update({"quantity": new_qty}) \
                    .eq("id", item_id) \
                    .execute()
                return res.data[0] if res.data else {}
            else:
                # Nếu chưa có -> Thêm mới và Ép giới hạn tồn kho
                if quantity > max_stock:
                    quantity = max_stock
                    
                res = db.table("cart_items").insert({
                    "user_id": user_id,
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": quantity
                }).execute()
                return res.data[0] if res.data else {}
                
        except Exception as e:
            logger.error(f"Lỗi add_item giỏ hàng: {e}")
            return {}

    @staticmethod
    def update_quantity(user_id: str, item_id: str, quantity: int) -> dict:
        """Cập nhật số lượng của 1 món hàng. Kiểm tra tồn kho trực tiếp."""
        if quantity <= 0:
            CartModel.remove_item(user_id, item_id)
            return {}

        db = CartModel._db()
        try:
            # Bước 1: Lấy thông tin item để biết nó đang liên kết với Variant nào
            item = db.table("cart_items").select("variant_id").eq("id", item_id).eq("user_id", user_id).execute()
            if not item.data:
                return {}
            
            variant_id = item.data[0]["variant_id"]
            
            # Bước 2: Soi tồn kho của Variant đó
            variant_check = db.table("product_variants").select("stock").eq("id", variant_id).execute()
            if variant_check.data:
                max_stock = variant_check.data[0].get("stock", 0)
                if quantity > max_stock:
                    quantity = max_stock  # Chống thủ thuật sửa HTML để tăng quantity lố kho
                    
            # Bước 3: Update
            res = db.table("cart_items") \
                .update({"quantity": quantity}) \
                .eq("id", item_id) \
                .eq("user_id", user_id) \
                .execute()
            return res.data[0] if res.data else {}
            
        except Exception as e:
            logger.error(f"Lỗi cập nhật số lượng item {item_id}: {e}")
            return {}

    @staticmethod
    def remove_item(user_id: str, item_id: str) -> bool:
        """Xóa một sản phẩm khỏi giỏ hàng. Có check user_id để bảo mật."""
        try:
            res = CartModel._db().table("cart_items") \
                .delete() \
                .eq("id", item_id) \
                .eq("user_id", user_id) \
                .execute()
            return len(res.data) > 0 if res.data else False
        except Exception as e:
            logger.error(f"Lỗi xóa item {item_id}: {e}")
            return False

    @staticmethod
    def clear_cart(user_id: str) -> bool:
        """Xóa sạch giỏ hàng (Sau khi thanh toán thành công)."""
        try:
            CartModel._db().table("cart_items") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi clear_cart cho user {user_id}: {e}")
            return False

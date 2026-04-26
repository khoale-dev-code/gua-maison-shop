import logging
from app.utils.supabase_client import get_supabase

# 1. Khởi tạo logger để fix lỗi "Undefined variable: logger"
logger = logging.getLogger(__name__)


class CartModel:

    @staticmethod
    def _db():
        """Helper lấy kết nối Supabase - Fix lỗi 'Undefined variable: get_supabase'"""
        return get_supabase()

    @staticmethod
    def add_item(user_id: str, product_id: str, quantity: int=1, size: str=None) -> dict:
        """
        Sử dụng RPC 'add_item_to_cart' để xử lý Atomic Upsert.
        Giải quyết triệt để Race Condition.
        """
        try:
            # Lưu ý: Tên tham số phải khớp chính xác với định nghĩa trong SQL Function
            res = CartModel._db().rpc("add_item_to_cart", {
                "p_user_id": user_id,
                "p_product_id": product_id,
                "p_quantity": quantity,
                "p_size": size or ""  # Tránh gửi null cho cột size
            }).execute()
            
            return res.data if res.data else {}
        except Exception as e:
            logger.error(f"Lỗi RPC add_item_to_cart: {e}")
            return {}

    @staticmethod
    def get_count(user_id: str) -> int:
        """Lấy tổng số lượng item cực nhanh thông qua RPC SQL SUM."""
        try:
            res = CartModel._db().rpc("get_cart_total_quantity", {
                "p_user_id": user_id
            }).execute()
            
            # Trả về kết quả trực tiếp từ hàm SQL
            return res.data if res.data else 0
        except Exception as e:
            logger.error(f"Lỗi RPC get_cart_total_quantity: {e}")
            return 0

    @staticmethod
    def get_cart(user_id: str) -> list:
        """Lấy danh sách sản phẩm trong giỏ kèm thông tin chi tiết."""
        try:
            result = CartModel._db().table("cart_items") \
                .select("*, products(id, name, price, thumbnail_url)") \
                .eq("user_id", user_id) \
                .order("created_at") \
                .execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Lỗi lấy giỏ hàng cho user {user_id}: {e}")
            return []

    @staticmethod
    def update_quantity(item_id: str, quantity: int) -> dict:
        """Cập nhật số lượng item. Nếu <= 0 thì tự động xóa."""
        if quantity <= 0:
            CartModel.remove_item(item_id)
            return {}

        try:
            result = CartModel._db().table("cart_items") \
                .update({"quantity": quantity}) \
                .eq("id", item_id) \
                .execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Lỗi cập nhật số lượng item {item_id}: {e}")
            return {}

    @staticmethod
    def remove_item(item_id: str) -> bool:
        """Xóa một sản phẩm khỏi giỏ hàng."""
        try:
            res = CartModel._db().table("cart_items") \
                .delete() \
                .eq("id", item_id) \
                .execute()
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"Lỗi xóa item {item_id}: {e}")
            return False

    @staticmethod
    def clear_cart(user_id: str) -> bool:
        """Xóa sạch giỏ hàng sau khi thanh toán thành công."""
        try:
            CartModel._db().table("cart_items") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi dọn dẹp giỏ hàng cho user {user_id}: {e}")
            return False

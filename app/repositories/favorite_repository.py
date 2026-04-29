import logging
from config.settings import get_supabase_client

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom Exception cho các lỗi liên quan đến Database"""
    pass


class FavoriteRepository:
    
    @staticmethod
    def toggle(user_id: str, product_id: str) -> str:
        """Thực hiện UPSERT logic: Cố gắng Insert, nếu lỗi Duplicate Key thì Delete"""
        supabase = get_supabase_client()
        
        try:
            # Cố gắng Insert
            supabase.table('favorites').insert({
                "user_id": user_id,
                "product_id": product_id
            }).execute()
            return "added"
            
        except Exception as e:
            # Chuyển toàn bộ lỗi thành chữ thường để dễ bóc tách
            error_str = str(e).lower()
            
            # Bắt LỖI TRÙNG LẶP (Duplicate/23505) - Tức là người dùng đã thả tim rồi
            if '23505' in error_str or 'duplicate' in error_str:
                # Nếu đã thả tim -> Chuyển sang hành động XÓA (Bỏ thả tim)
                supabase.table('favorites').delete().eq('user_id', user_id).eq('product_id', product_id).execute()
                return "removed"
                
            # Nếu không phải lỗi trùng lặp, IN ĐỎ ra màn hình Terminal của VS Code để ta dễ debug
            logger.error(f"🔴 [DB_ERROR] Lỗi thực sự từ Supabase: {error_str}")
            raise DatabaseError("Lỗi hệ thống khi thao tác dữ liệu.") from e

    @staticmethod
    def get_user_favorites(user_id: str, limit: int=20, offset: int=0) -> list:
        supabase = get_supabase_client()
        try:
            response = supabase.table('favorites')\
                .select('*, products(*)')\
                .eq('user_id', user_id)\
                .range(offset, offset + limit - 1)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"[DB_ERROR] Fetching favorites for user {user_id}: {e}")
            raise

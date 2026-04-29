import logging
from app.repositories.favorite_repository import FavoriteRepository

logger = logging.getLogger(__name__)


class FavoriteService:
    
    @staticmethod
    def toggle_favorite(user_id: str, product_id: str) -> dict:
        try:
            action = FavoriteRepository.toggle(user_id, product_id)
            return {"status": "success", "action": action}
        except Exception as e:
            logger.error(f"[SERVICE_ERROR] Toggle favorite failed: {e}")
            # Quăng lỗi ValueError để Controller dễ dàng bắt và trả về HTTP 400
            raise ValueError("Không thể cập nhật danh sách yêu thích lúc này.")

    @staticmethod
    def get_user_wishlist(user_id: str, page: int=1, per_page: int=20) -> list:
        # Tính toán Pagination
        offset = (page - 1) * per_page
        
        # [TƯƠNG LAI] Có thể check Redis Cache ở đây: 
        # cached_data = redis.get(f"wishlist:{user_id}:page:{page}")
        
        raw_data = FavoriteRepository.get_user_favorites(user_id, limit=per_page, offset=offset)
        
        # [TƯƠNG LAI] Map raw_data sang FavoriteDTO trước khi trả về
        return raw_data

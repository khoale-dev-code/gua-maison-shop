    
from config.settings import get_supabase_client


class FavoriteModel:

    @staticmethod
    def toggle_favorite(user_id: str, product_id: str):
        supabase = get_supabase_client()
        
        # Kiểm tra xem đã yêu thích chưa
        existing = supabase.table('favorites').select('*').eq('user_id', user_id).eq('product_id', product_id).execute()
        
        if existing.data:
            # Nếu đã có -> Xóa (Bỏ yêu thích)
            supabase.table('favorites').delete().eq('user_id', user_id).eq('product_id', product_id).execute()
            return {"status": "removed"}
        else:
            # Nếu chưa có -> Thêm mới (Yêu thích)
            supabase.table('favorites').insert({
                "user_id": user_id,
                "product_id": product_id
            }).execute()
            return {"status": "added"}

    @staticmethod
    def get_user_favorites(user_id: str):
        supabase = get_supabase_client()
        # Lấy danh sách yêu thích kèm theo thông tin chi tiết của bảng products
        response = supabase.table('favorites').select('*, products(*)').eq('user_id', user_id).execute()
        return response.data

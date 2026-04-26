"""
app/models/category_model.py  –  CRUD danh mục (Optimized Edition)
"""
import logging
from typing import List, Dict, Optional
from app.utils.supabase_client import get_supabase

# Khởi tạo logger để bắt lỗi hệ thống (rất quan trọng khi Debug)
logger = logging.getLogger(__name__)


class CategoryModel:
    # 1. TỐI ƯU HIỆU NĂNG: Khởi tạo kết nối DB một lần dùng chung cho toàn Class
    db = get_supabase()

    @staticmethod
    def get_all() -> List[Dict]:
        try:
            r = CategoryModel.db.table("categories").select("*").order("name").execute()
            return r.data
        except Exception:
            logger.exception("Lỗi truy vấn danh sách danh mục (get_all)")
            return []

    @staticmethod
    def get_by_id(cid: str) -> Optional[Dict]:
        try:
            r = CategoryModel.db.table("categories").select("*").eq("id", cid).limit(1).execute()
            return r.data[0] if r.data else None
        except Exception:
            logger.exception(f"Lỗi lấy thông tin danh mục ID: {cid}")
            return None

    @staticmethod
    def create(name: str, slug: str) -> Dict:
        try:
            r = CategoryModel.db.table("categories").insert({"name": name, "slug": slug}).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception(f"Lỗi tạo danh mục mới: {name}")
            return {}

    @staticmethod
    def update(cid: str, name: str, slug: str) -> Dict:
        try:
            r = CategoryModel.db.table("categories").update({"name": name, "slug": slug}).eq("id", cid).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception(f"Lỗi cập nhật danh mục ID: {cid}")
            return {}

    @staticmethod
    def delete(cid: str) -> bool:
        try:
            # Lưu ý hệ thống: Nếu bảng products có khóa ngoại (foreign key) cascade, 
            # xóa danh mục sẽ báo lỗi (hoặc xóa luôn sản phẩm). Hãy cấu hình ở DB cẩn thận.
            r = CategoryModel.db.table("categories").delete().eq("id", cid).execute()
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi xóa danh mục ID: {cid}")
            return False

    @staticmethod
    def slug_exists(slug: str, exclude_id: str=None) -> bool:
        try:
            q = CategoryModel.db.table("categories").select("id").eq("slug", slug)
            if exclude_id:
                q = q.neq("id", exclude_id)
            
            r = q.limit(1).execute()
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi kiểm tra tồn tại slug: {slug}")
            return False

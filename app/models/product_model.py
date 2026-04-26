import logging
from typing import Dict, List, Any, Optional
from app.utils.supabase_client import get_supabase

# Khởi tạo logger để ghi lại stack trace khi có lỗi
logger = logging.getLogger(__name__)


class ProductModel:
    # 1. Tối ưu: Dùng chung một kết nối duy nhất trong Class
    db = get_supabase()

    # SỬA LỖI: Supabase Python client dùng 'desc' thay vì 'ascending' hay 'descending'
    ALLOWED_SORT = {
        "price_asc": ("price", {"desc": False}),
        "price_desc": ("price", {"desc": True}),
        "newest": ("created_at", {"desc": True})
    }

    @staticmethod
    def get_all(page: int=1,
                per_page: int=12,
                category: Optional[str]=None,
                keyword: Optional[str]=None,
                sort: Optional[str]="newest",
                admin_mode: bool=False) -> Dict[str, Any]:
        """
        Hàm lấy danh sách sản phẩm tổng hợp: Hỗ trợ Filter, Search, Sort và Phân trang.
        Sử dụng kỹ thuật !inner join để lọc theo slug danh mục trong 1 lần query.
        """
        try:
            offset = (page - 1) * per_page
            
            # Khởi tạo query. !inner giúp filter dựa trên bảng liên kết (categories)
            select_query = "*, categories!inner(name, slug)"
            q = ProductModel.db.table("products").select(select_query, count="exact")

            # 2. Xử lý Soft Delete (Admin thấy hết, User chỉ thấy active)
            if not admin_mode:
                q = q.eq("is_active", True)

            # 3. Tối ưu: Lọc theo Category Slug trực tiếp bằng Nested Filter (Không gọi DB 2 lần)
            if category:
                q = q.eq("categories.slug", category)

            # 4. Tìm kiếm từ khóa
            if keyword:
                q = q.ilike("name", f"%{keyword}%")

            # 5. Validate và xử lý Sort
            sort_config = ProductModel.ALLOWED_SORT.get(sort, ProductModel.ALLOWED_SORT["newest"])
            q = q.order(sort_config[0], **sort_config[1])

            # 6. Thực thi phân trang
            r = q.range(offset, offset + per_page - 1).execute()

            return {
                "items": r.data,
                "total": r.count or 0,
                "page": page,
                "per_page": per_page
            }
        except Exception:
            logger.exception(f"Lỗi truy vấn danh sách sản phẩm. Page: {page}")
            return {"items": [], "total": 0}

    @staticmethod
    def get_by_id(pid: str) -> Optional[Dict]:
        """Lấy chi tiết sản phẩm theo ID."""
        try:
            r = ProductModel.db.table("products").select("*, categories(name)") \
                .eq("id", pid).limit(1).execute()
            return r.data[0] if r.data else None
        except Exception:
            logger.exception(f"Lỗi lấy chi tiết sản phẩm ID: {pid}")
            return None

    @staticmethod
    def get_featured(limit: int=8) -> List[Dict]:
        """Lấy danh sách sản phẩm nổi bật cho trang chủ."""
        try:
            # SỬA LỖI CRASH: Dùng desc=True thay vì descending=True
            r = ProductModel.db.table("products").select("*") \
                .eq("is_featured", True) \
                .eq("is_active", True) \
                .order("created_at", desc=True) \
                .limit(limit).execute()
            return r.data
        except Exception:
            logger.exception("Lỗi lấy sản phẩm nổi bật")
            return []

    @staticmethod
    def create(data: Dict[str, Any]) -> Dict:
        """Tạo sản phẩm mới."""
        try:
            r = ProductModel.db.table("products").insert(data).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception("Lỗi tạo sản phẩm")
            return {}

    @staticmethod
    def update(pid: str, data: Dict[str, Any]) -> Dict:
        """Cập nhật thông tin sản phẩm."""
        try:
            r = ProductModel.db.table("products").update(data).eq("id", pid).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception(f"Lỗi cập nhật sản phẩm ID: {pid}")
            return {}

    @staticmethod
    def delete(pid: str) -> bool:
        """
        Soft delete: Đánh dấu is_active = False.
        Trả về True nếu thực sự có bản ghi bị tác động.
        """
        try:
            r = ProductModel.db.table("products") \
                .update({"is_active": False}) \
                .eq("id", pid).execute()
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi xóa sản phẩm ID: {pid}")
            return False

    @staticmethod
    def count_by_category() -> List[Dict]:
        """
        Thống kê số lượng sản phẩm mỗi danh mục cho Dashboard.
        Tối ưu: Chỉ lấy trường cần thiết.
        """
        try:
            r = ProductModel.db.table("products").select("categories(name)") \
                .eq("is_active", True).execute()
            
            from collections import Counter
            counts = Counter([item["categories"]["name"] for item in r.data if item.get("categories")])
            
            return [{"name": k, "count": v} for k, v in counts.items()]
        except Exception:
            logger.exception("Lỗi thống kê danh mục")
            return []

import logging
from typing import Dict, List, Any, Optional
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class ProductModel:
    db = get_supabase()

    ALLOWED_SORT = {
        "price_asc": ("price", {"desc": False}),
        "price_desc": ("price", {"desc": True}),
        "newest": ("created_at", {"desc": True}),
    }

    # ─── DANH SÁCH SẢN PHẨM ───────────────────────────────────────

    @staticmethod
    def get_all(
        page: int=1,
        per_page: int=12,
        category: Optional[str]=None,
        keyword: Optional[str]=None,
        sort: Optional[str]="newest",
        admin_mode: bool=False,
    ) -> Dict[str, Any]:
        """Lấy danh sách sản phẩm có filter, search, sort và phân trang."""
        try:
            offset = (page - 1) * per_page
            q = ProductModel.db.table("products").select(
                "*, categories!inner(name, slug)", count="exact"
            )

            if not admin_mode:
                q = q.eq("is_active", True)
            if category:
                q = q.eq("categories.slug", category)
            if keyword:
                q = q.ilike("name", f"%{keyword}%")

            sort_col, sort_opts = ProductModel.ALLOWED_SORT.get(
                sort, ProductModel.ALLOWED_SORT["newest"]
            )
            r = q.order(sort_col, **sort_opts).range(offset, offset + per_page - 1).execute()

            return {"items": r.data, "total": r.count or 0, "page": page, "per_page": per_page}
        except Exception:
            logger.exception(f"Lỗi get_all. Page={page}")
            return {"items": [], "total": 0}

    # ─── CHI TIẾT SẢN PHẨM ────────────────────────────────────────

    @staticmethod
    def get_by_id(pid: str) -> Optional[Dict]:
        """Lấy chi tiết sản phẩm kèm danh sách ảnh (sắp xếp theo sort_order)."""
        try:
            r = (
                ProductModel.db.table("products")
                .select("*, categories(name, slug)")
                .eq("id", pid)
                .limit(1)
                .execute()
            )
            if not r.data:
                return None

            product = r.data[0]
            product["images"] = ProductModel.get_images(pid)
            return product
        except Exception:
            logger.exception(f"Lỗi get_by_id. ID={pid}")
            return None

    # ─── SẢN PHẨM NỔI BẬT ────────────────────────────────────────

    @staticmethod
    def get_featured(limit: int=8) -> List[Dict]:
        """Lấy sản phẩm nổi bật cho trang chủ, kèm ảnh đầu tiên."""
        try:
            r = (
                ProductModel.db.table("products")
                .select("*")
                .eq("is_featured", True)
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            products = r.data
            # Gắn ảnh primary (hoặc ảnh đầu tiên) vào từng sản phẩm
            for p in products:
                imgs = ProductModel.get_images(p["id"])
                p["images"] = imgs
            return products
        except Exception:
            logger.exception("Lỗi get_featured")
            return []

    # ─── TẠO / CẬP NHẬT / XÓA SẢN PHẨM ─────────────────────────

    @staticmethod
    def create(data: Dict[str, Any]) -> Dict:
        """Tạo sản phẩm mới."""
        try:
            r = ProductModel.db.table("products").insert(data).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception("Lỗi create product")
            return {}

    @staticmethod
    def update(pid: str, data: Dict[str, Any]) -> Dict:
        """Cập nhật thông tin sản phẩm."""
        try:
            r = ProductModel.db.table("products").update(data).eq("id", pid).execute()
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception(f"Lỗi update product. ID={pid}")
            return {}

    @staticmethod
    def delete(pid: str) -> bool:
        """Soft delete: đánh dấu is_active = False."""
        try:
            r = ProductModel.db.table("products").update({"is_active": False}).eq("id", pid).execute()
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi delete product. ID={pid}")
            return False

    # ─── QUẢN LÝ ẢNH SẢN PHẨM ────────────────────────────────────

    @staticmethod
    def get_images(pid: str) -> List[Dict]:
        """Lấy toàn bộ ảnh của 1 sản phẩm, sắp xếp theo sort_order tăng dần."""
        try:
            r = (
                ProductModel.db.table("product_images")
                .select("*")
                .eq("product_id", pid)
                .order("sort_order", desc=False)
                .execute()
            )
            return r.data or []
        except Exception:
            logger.exception(f"Lỗi get_images. Product ID={pid}")
            return []

    @staticmethod
    def add_image(pid: str, url: str, is_primary: bool=False, sort_order: int=0) -> Dict:
        """Thêm 1 ảnh vào sản phẩm."""
        try:
            # Nếu đánh dấu là ảnh chính → bỏ flag primary của các ảnh cũ
            if is_primary:
                ProductModel._clear_primary(pid)

            r = (
                ProductModel.db.table("product_images")
                .insert({
                    "product_id": pid,
                    "url": url,
                    "is_primary": is_primary,
                    "sort_order": sort_order,
                })
                .execute()
            )
            return r.data[0] if r.data else {}
        except Exception:
            logger.exception(f"Lỗi add_image. Product ID={pid}")
            return {}

    @staticmethod
    def delete_image(image_id: str) -> bool:
        """Xóa 1 ảnh theo image_id."""
        try:
            r = ProductModel.db.table("product_images").delete().eq("id", image_id).execute()
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi delete_image. Image ID={image_id}")
            return False

    @staticmethod
    def set_primary_image(image_id: str, pid: str) -> bool:
        """Đặt 1 ảnh làm ảnh chính, bỏ flag primary của các ảnh còn lại."""
        try:
            ProductModel._clear_primary(pid)
            r = (
                ProductModel.db.table("product_images")
                .update({"is_primary": True})
                .eq("id", image_id)
                .execute()
            )
            return bool(r.data)
        except Exception:
            logger.exception(f"Lỗi set_primary_image. Image ID={image_id}")
            return False

    @staticmethod
    def reorder_images(image_orders: List[Dict]) -> bool:
        """
        Cập nhật sort_order cho nhiều ảnh cùng lúc.
        image_orders: [{"id": "uuid", "sort_order": 0}, ...]
        """
        try:
            for item in image_orders:
                ProductModel.db.table("product_images").update(
                    {"sort_order": item["sort_order"]}
                ).eq("id", item["id"]).execute()
            return True
        except Exception:
            logger.exception("Lỗi reorder_images")
            return False

    @staticmethod
    def sync_images(pid: str, urls: List[str]) -> None:
        """
        Đồng bộ toàn bộ ảnh của 1 sản phẩm từ danh sách URL:
        - Thêm URL mới chưa có trong DB.
        - Giữ nguyên URL đã tồn tại (không xóa để bảo toàn is_primary / sort_order).
        - Xóa URL không còn trong danh sách.
        """
        try:
            existing = ProductModel.get_images(pid)
            existing_urls = {img["url"] for img in existing}
            submitted_urls = set(urls)

            # Thêm ảnh mới
            for idx, url in enumerate(urls):
                if url and url not in existing_urls:
                    is_first = (idx == 0 and not existing_urls)
                    ProductModel.add_image(pid, url, is_primary=is_first, sort_order=idx)

            # Xóa ảnh không còn trong danh sách
            for img in existing:
                if img["url"] not in submitted_urls:
                    ProductModel.delete_image(img["id"])

            # Cập nhật sort_order theo thứ tự form
            updated = ProductModel.get_images(pid)
            url_to_img = {img["url"]: img for img in updated}
            for idx, url in enumerate(urls):
                if url and url in url_to_img:
                    ProductModel.db.table("product_images").update(
                        {"sort_order": idx}
                    ).eq("id", url_to_img[url]["id"]).execute()

        except Exception:
            logger.exception(f"Lỗi sync_images. Product ID={pid}")

    # ─── UPLOAD LÊN SUPABASE STORAGE ─────────────────────────────

    @staticmethod
    def upload_to_storage(file_bytes: bytes, filename: str, content_type: str) -> Optional[str]:
        """
        Upload file ảnh lên Supabase Storage bucket 'product-images'.
        Trả về public URL nếu thành công, None nếu thất bại.
        """
        import uuid
        try:
            # Tạo tên file duy nhất để tránh trùng lặp
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
            unique_name = f"{uuid.uuid4().hex}.{ext}"

            ProductModel.db.storage.from_("product-images").upload(
                path=unique_name,
                file=file_bytes,
                file_options={"content-type": content_type},
            )

            # Lấy public URL
            result = ProductModel.db.storage.from_("product-images").get_public_url(unique_name)
            return result
        except Exception:
            logger.exception(f"Lỗi upload_to_storage. File={filename}")
            return None

    # ─── THỐNG KÊ ─────────────────────────────────────────────────

    @staticmethod
    def count_by_category() -> List[Dict]:
        """Thống kê số lượng sản phẩm mỗi danh mục cho Dashboard."""
        try:
            from collections import Counter
            r = (
                ProductModel.db.table("products")
                .select("categories(name)")
                .eq("is_active", True)
                .execute()
            )
            counts = Counter(
                item["categories"]["name"]
                for item in r.data
                if item.get("categories")
            )
            return [{"name": k, "count": v} for k, v in counts.items()]
        except Exception:
            logger.exception("Lỗi count_by_category")
            return []

    # ─── PRIVATE HELPERS ──────────────────────────────────────────

    @staticmethod
    def _clear_primary(pid: str) -> None:
        """Bỏ flag is_primary của tất cả ảnh thuộc sản phẩm."""
        ProductModel.db.table("product_images").update(
            {"is_primary": False}
        ).eq("product_id", pid).execute()

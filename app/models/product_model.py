"""
app/models/product_model.py
Quản lý dữ liệu Sản phẩm, Biến thể (Variants) và SEO chuẩn E-commerce.
Hỗ trợ Soft Delete, Slug generation và đồng bộ hình ảnh.
"""

import logging
import re
from datetime import datetime
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class ProductModel:

    @staticmethod
    def _db():
        return get_supabase()

    # ═══════════════════════════════════════════════════════════════
    #  SLUG HELPERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def generate_slug(name: str) -> str:
        """Tạo slug không dấu: 'Áo Thun GUA' -> 'ao-thun-gua'"""
        if not name:
            return ""
        slug = name.lower()
        slug = re.sub(r'[áàảãạăắằẳẵặâấầẩẫậ]', 'a', slug)
        slug = re.sub(r'[éèẻẽẹêếềểễệ]', 'e', slug)
        slug = re.sub(r'[íìỉĩị]', 'i', slug)
        slug = re.sub(r'[óòỏõọôốồổỗộơớờởỡợ]', 'o', slug)
        slug = re.sub(r'[úùủũụưứừửữự]', 'u', slug)
        slug = re.sub(r'[ýỳỷỹỵ]', 'y', slug)
        slug = re.sub(r'[đ]', 'd', slug)
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s-]+', '-', slug).strip('-')
        return slug

    @staticmethod
    def fix_missing_slugs() -> int:
        """
        Backfill slug cho các sản phẩm bị thiếu trong DB.
        Trả về số sản phẩm đã được fix.
        """
        db = ProductModel._db()
        fixed = 0
        try:
            # Lấy tất cả sản phẩm thiếu slug (NULL, rỗng hoặc chuỗi 'None')
            res = db.table("products").select("id, name, slug").execute()
            for p in (res.data or []):
                slug_val = p.get("slug")
                if slug_val and slug_val not in ("None", "null", ""):
                    continue  # Slug đã hợp lệ, bỏ qua
                new_slug = ProductModel.generate_slug(p.get("name", ""))
                if not new_slug:
                    continue
                db.table("products").update({"slug": new_slug}).eq("id", p["id"]).execute()
                logger.info(f"Fixed slug: '{p['name']}' -> '{new_slug}'")
                fixed += 1
            return fixed
        except Exception as e:
            logger.error(f"Lỗi fix_missing_slugs: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════
    #  READ
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_all(
        page: int=1,
        per_page: int=12,
        category_slug: str=None,
        gender: str=None,
        keyword: str=None,
        admin_mode: bool=False,
    ) -> dict:
        """
        Lấy danh sách sản phẩm có phân trang và bộ lọc.
        admin_mode=True  → lấy cả sản phẩm đã ẩn / soft-deleted.
        admin_mode=False → chỉ lấy sản phẩm active, chưa xóa.
        """
        db = ProductModel._db()
        offset = (page - 1) * per_page

        try:
            query = db.table("products").select(
                "*, categories(name, slug)", count="exact"
            )

            if not admin_mode:
                query = query.is_("deleted_at", "null").eq("is_active", True)

            if category_slug:
                query = query.eq("category_slug", category_slug)

            if gender:
                query = query.eq("gender", gender)

            if keyword:
                query = query.ilike("name", f"%{keyword}%")

            res = (
                query.order("created_at", desc=True)
                .range(offset, offset + per_page - 1)
                .execute()
            )

            items = res.data or []
            for item in items:
                if not item.get("thumbnail_url"):
                    item["thumbnail_url"] = (
                        "https://placehold.co/400x500?text=No+Image"
                    )

            return {
                "items": items,
                "total": res.count or 0,
                "page": page,
                "per_page": per_page,
            }
        except Exception as e:
            logger.error(f"Lỗi get_all products: {e}")
            return {"items": [], "total": 0}

    @staticmethod
    def get_by_id(pid: str):
        """
        Lấy chi tiết sản phẩm kèm Ảnh và Biến thể.
        Dùng .limit(1) thay .single() để tránh crash khi không tìm thấy.
        """
        if not pid:
            return None
        db = ProductModel._db()
        try:
            res = (
                db.table("products")
                .select("*, categories(name), product_images(*), product_variants(*)")
                .eq("id", pid)
                .limit(1)
                .execute()
            )

            if not res.data:
                return None

            product = res.data[0]

            # Sắp xếp ảnh theo sort_order
            product["product_images"] = sorted(
                product.get("product_images") or [],
                key=lambda x: x.get("sort_order", 0),
            )

            # Fallback thumbnail
            if not product.get("thumbnail_url"):
                images = product["product_images"]
                primary = next(
                    (img["url"] for img in images if img.get("is_primary")), None
                )
                product["thumbnail_url"] = (
                    primary
                    or (images[0]["url"] if images else "https://placehold.co/400x500?text=No+Image")
                )

            return product
        except Exception as e:
            logger.error(f"Lỗi get_by_id product '{pid}': {e}")
            return None

    @staticmethod
    def get_by_slug(slug: str):
        """
        Lấy sản phẩm qua Slug (SEO Friendly).
        Dùng .limit(1) thay .single() để tránh crash khi không tìm thấy.
        """
        if not slug or slug in ("None", "null", "undefined", ""):
            return None
        db = ProductModel._db()
        try:
            res = (
                db.table("products")
                .select("*, categories(name, slug), product_images(*), product_variants(*)")
                .eq("slug", slug)
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
            )

            if not res.data:
                return None

            product = res.data[0]

            # Sắp xếp ảnh theo sort_order
            product["product_images"] = sorted(
                product.get("product_images") or [],
                key=lambda x: x.get("sort_order", 0),
            )

            # Fallback thumbnail
            if not product.get("thumbnail_url"):
                images = product["product_images"]
                primary = next(
                    (img["url"] for img in images if img.get("is_primary")), None
                )
                product["thumbnail_url"] = (
                    primary
                    or (images[0]["url"] if images else "https://placehold.co/400x500?text=No+Image")
                )

            return product
        except Exception as e:
            logger.error(f"Lỗi get_by_slug '{slug}': {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    #  WRITE
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def create(data: dict) -> dict:
        """Tạo sản phẩm mới, tự động tạo slug nếu thiếu."""
        db = ProductModel._db()

        # Đảm bảo slug không bao giờ bị None
        if not data.get("slug") and data.get("name"):
            data["slug"] = ProductModel.generate_slug(data["name"])

        try:
            res = db.table("products").insert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Lỗi tạo sản phẩm: {e}")
            return None

    @staticmethod
    def update(pid: str, data: dict) -> bool:
        """Cập nhật thông tin sản phẩm."""
        if not pid:
            return False

        # Đảm bảo slug không bị xóa/None khi update
        if "slug" in data and not data["slug"]:
            data.pop("slug")  # Bỏ qua field slug nếu trống, giữ nguyên giá trị cũ

        try:
            res = (
                ProductModel._db()
                .table("products")
                .update(data)
                .eq("id", pid)
                .execute()
            )
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"Lỗi cập nhật sản phẩm '{pid}': {e}")
            return False

    @staticmethod
    def delete(pid: str, permanent: bool=False) -> bool:
        """
        Xóa sản phẩm.
        permanent=False (default) → Soft Delete (set deleted_at + is_active=False).
        permanent=True            → Hard Delete (xóa hẳn khỏi DB).
        """
        db = ProductModel._db()
        try:
            if permanent:
                res = db.table("products").delete().eq("id", pid).execute()
            else:
                res = db.table("products").update({
                    "deleted_at": datetime.now().isoformat(),
                    "is_active": False,
                }).eq("id", pid).execute()
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"Lỗi xóa sản phẩm '{pid}': {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    #  IMAGES
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_images(pid: str) -> list:
        """Lấy danh sách ảnh của sản phẩm, sắp xếp theo sort_order."""
        try:
            res = (
                ProductModel._db()
                .table("product_images")
                .select("*")
                .eq("product_id", pid)
                .order("sort_order")
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Lỗi get_images '{pid}': {e}")
            return []

    @staticmethod
    def sync_images(pid: str, urls: list) -> bool:
        """
        Đồng bộ danh sách ảnh: xóa ảnh cũ rồi insert mới.
        Ảnh đầu tiên tự động làm ảnh primary (bìa).
        """
        db = ProductModel._db()
        try:
            db.table("product_images").delete().eq("product_id", pid).execute()

            if urls:
                image_data = [
                    {
                        "product_id": pid,
                        "url": url,
                        "sort_order": i,
                        "is_primary": (i == 0),
                    }
                    for i, url in enumerate(urls)
                ]
                db.table("product_images").insert(image_data).execute()

            return True
        except Exception as e:
            logger.error(f"Lỗi sync_images cho '{pid}': {e}")
            return False

    @staticmethod
    def upload_to_storage(file_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload file lên Supabase Storage và trả về public URL."""
        db = ProductModel._db()
        try:
            # Thêm timestamp để tránh trùng tên file
            path = f"products/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            db.storage.from_("products").upload(
                path, file_bytes, {"content-type": content_type}
            )
            return db.storage.from_("products").get_public_url(path)
        except Exception as e:
            logger.error(f"Lỗi upload storage: {e}")
            return ""

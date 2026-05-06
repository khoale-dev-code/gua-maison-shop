"""
app/models/product_model.py
Quản lý dữ liệu Sản phẩm, Biến thể (Variants) và SEO chuẩn E-commerce.
Hỗ trợ Soft Delete, Slug generation, tự động tính Discount và đồng bộ hình ảnh.
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
    #  UTILITIES & FORMATTERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def generate_slug(name: str) -> str:
        """Tạo slug không dấu chuẩn SEO: 'Áo Thun GUA' -> 'ao-thun-gua'"""
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
    def _format_product(product: dict) -> dict:
        """
        Hàm dùng chung để format dữ liệu 1 sản phẩm: 
        Sắp xếp ảnh, gán ảnh fallback, tính % giảm giá cho UI.
        """
        if not product:
            return product

        # 1. Xử lý hình ảnh
        imgs = sorted(product.get("product_images") or [], key=lambda x: x.get("sort_order", 0))
        product["product_images"] = imgs
        product["images"] = imgs  # Đồng bộ biến "images" cho Jinja2 UI
        
        # 2. Logic Fallback an toàn cho ảnh bìa (thumbnail)
        if not product.get("thumbnail_url"):
            primary = next((img["url"] for img in imgs if img.get("is_primary")), None)
            # Dùng placehold.co với tone màu xám Studio nếu không có ảnh
            product["thumbnail_url"] = primary or (imgs[0]["url"] if imgs else "https://placehold.co/600x800/f8f8f8/cccccc?text=GUA")

        # 3. Tự động tính phần trăm giảm giá (Discount Percent) cho UI
        price = product.get("price")
        old_price = product.get("old_price")
        if price and old_price and old_price > price:
            percent = int(100 - (price / old_price * 100))
            product["discount_percent"] = percent
        else:
            product["discount_percent"] = None

        return product

    @staticmethod
    def fix_missing_slugs() -> int:
        """Backfill slug cho các sản phẩm bị thiếu trong DB."""
        db = ProductModel._db()
        fixed = 0
        try:
            res = db.table("products").select("id, name, slug").execute()
            for p in (res.data or []):
                slug_val = p.get("slug")
                if slug_val and slug_val not in ("None", "null", ""):
                    continue
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
    #  READ (GET)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_categories(limit: int=3) -> list:
        """Lấy danh sách Danh mục nổi bật cho trang chủ."""
        db = ProductModel._db()
        try:
            # Nếu DB bạn có cột is_active cho bảng categories, có thể thêm .eq("is_active", True)
            res = db.table("categories").select("*").limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Lỗi get_categories: {e}")
            return []

    @staticmethod
    def get_featured(limit: int=8) -> list:
        """Lấy danh sách sản phẩm nổi bật / mới nhất cho trang chủ (Swiper UI)."""
        db = ProductModel._db()
        try:
            res = (
                db.table("products")
                .select("*, categories(name, slug), product_images(*), product_variants(*)")
                .is_("deleted_at", "null")
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            items = res.data or []
            return [ProductModel._format_product(item) for item in items]
        except Exception as e:
            logger.error(f"Lỗi get_featured: {e}")
            return []

    @staticmethod
    def get_all(
        page: int=1,
        per_page: int=12,
        category_slug: str=None,
        gender: str=None,
        keyword: str=None,
        admin_mode: bool=False,
    ) -> dict:
        """Lấy danh sách sản phẩm có phân trang và bộ lọc (Dùng cho trang Cửa hàng)."""
        db = ProductModel._db()
        offset = (page - 1) * per_page

        try:
            query = db.table("products").select(
                "*, categories(name, slug), product_variants(*), product_images(*)", count="exact"
            )

            if not admin_mode:
                query = query.is_("deleted_at", "null").eq("is_active", True)

            # ── Filter theo danh mục ──
            if category_slug:
                try:
                    cat_res = db.table("categories").select("id").eq("slug", category_slug).limit(1).execute()
                    if cat_res.data:
                        category_id = cat_res.data[0]["id"]
                        query = query.eq("category_id", category_id)
                    else:
                        return {"items": [], "total": 0, "page": page, "per_page": per_page}
                except Exception as cat_err:
                    logger.error(f"Lỗi resolve category_slug '{category_slug}': {cat_err}")

            if gender:
                query = query.eq("gender", gender)

            if keyword:
                query = query.ilike("name", f"%{keyword}%")

            res = (
                query.order("created_at", desc=True)
                .range(offset, offset + per_page - 1)
                .execute()
            )

            items = [ProductModel._format_product(item) for item in (res.data or [])]

            return {
                "items": items,
                "total": res.count or 0,
                "page": page,
                "per_page": per_page,
            }
        except Exception as e:
            logger.error(f"Lỗi get_all products: {e}")
            return {"items": [], "total": 0, "page": page, "per_page": per_page}

    @staticmethod
    def get_by_id(pid: str):
        if not pid:
            return None
        db = ProductModel._db()
        try:
            res = (
                db.table("products")
                .select("*, categories(name, slug), product_images(*), product_variants(*)")
                .eq("id", pid)
                .limit(1)
                .execute()
            )
            return ProductModel._format_product(res.data[0]) if res.data else None
        except Exception as e:
            logger.error(f"Lỗi get_by_id product '{pid}': {e}")
            return None

    @staticmethod
    def get_by_slug(slug: str):
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
            return ProductModel._format_product(res.data[0]) if res.data else None
        except Exception as e:
            logger.error(f"Lỗi get_by_slug '{slug}': {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    #  WRITE (POST / PUT / DELETE)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def create(data: dict) -> dict:
        db = ProductModel._db()
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
        if not pid:
            return False

        if "slug" in data and not data["slug"]:
            data.pop("slug") 

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
    #  IMAGES PROCESSING
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_images(pid: str) -> list:
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
        db = ProductModel._db()
        try:
            path = f"products/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            db.storage.from_("products").upload(
                path, file_bytes, {"content-type": content_type}
            )
            return db.storage.from_("products").get_public_url(path)
        except Exception as e:
            logger.error(f"Lỗi upload storage: {e}")
            return ""

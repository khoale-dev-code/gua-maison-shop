"""
app/models/product_model.py
Quản lý dữ liệu Sản phẩm, Biến thể (Variants) và SEO chuẩn E-commerce.
Hỗ trợ Soft Delete, Slug generation, Barcode generation, và đồng bộ hình ảnh.
"""

import logging
import re
import uuid
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
    def generate_barcode(product_id: str=None) -> str:
        """
        Sinh mã vạch duy nhất theo format: GUA-YYMM-XXXXXX
        - GUA     : Thương hiệu
        - YYMM    : Năm + Tháng tạo (VD: 2605 = tháng 5/2026)
        - XXXXXX  : 6 ký tự hex đầu của UUID (lấy từ product_id nếu có)

        Ví dụ: GUA-2605-A3F9C1
        """
        now = datetime.now()
        prefix = f"GUA-{now.strftime('%y%m')}"

        if product_id:
            hex_part = product_id.replace("-", "")[:6].upper()
        else:
            hex_part = uuid.uuid4().hex[:6].upper()

        return f"{prefix}-{hex_part}"

    # Bảng từ điển màu chuẩn Fashion
    COLOR_DICT = {
        'đen': '#000000', 'black': '#000000',
        'trắng': '#ffffff', 'white': '#ffffff',
        'đỏ': '#dc2626', 'red': '#dc2626',
        'xanh dương': '#2563eb', 'blue': '#2563eb',
        'xanh navy': '#1e3a8a', 'navy': '#1e3a8a',
        'xanh lá': '#16a34a', 'green': '#16a34a',
        'vàng': '#eab308', 'yellow': '#eab308',
        'cam': '#ea580c', 'orange': '#ea580c',
        'hồng': '#ec4899', 'pink': '#ec4899',
        'tím': '#9333ea', 'purple': '#9333ea',
        'xám': '#6b7280', 'gray': '#6b7280', 'grey': '#6b7280',
        'nâu': '#78350f', 'brown': '#78350f',
        'be': '#f5f5dc', 'beige': '#f5f5dc',
        'kem': '#fef3c7', 'cream': '#fef3c7'
    }

    @staticmethod
    def _format_product(product: dict) -> dict:
        """Format dữ liệu 1 sản phẩm: sắp xếp ảnh, tính giảm giá, map màu."""
        if not product:
            return product

        imgs = sorted(product.get("product_images") or [], key=lambda x: x.get("sort_order", 0))
        product["product_images"] = imgs
        product["images"] = imgs

        if not product.get("thumbnail_url"):
            primary = next((img["url"] for img in imgs if img.get("is_primary")), None)
            product["thumbnail_url"] = primary or (imgs[0]["url"] if imgs else "https://placehold.co/600x800/f8f8f8/cccccc?text=GUA")

        price = product.get("price")
        old_price = product.get("old_price")
        if price and old_price and old_price > price:
            product["discount_percent"] = int(100 - (price / old_price * 100))
        else:
            product["discount_percent"] = None

        variants = product.get("product_variants") or []
        for v in variants:
            c_hex = v.get("color_hex")
            if not c_hex or c_hex == "#1a1a1a":
                c_name = (v.get("color_name") or "").lower().strip()
                v["color_hex"] = ProductModel.COLOR_DICT.get(c_name, "#e5e5e5")
        product["product_variants"] = variants

        return product

    @staticmethod
    def fix_missing_slugs() -> int:
        """Backfill slug cho các sản phẩm bị thiếu trong DB."""
        db = ProductModel._db()
        fixed = 0
        try:
            res = db.table("products").select("id, name, slug").execute()
            for p in (res.data or []):
                if p.get("slug") and p["slug"] not in ("None", "null", ""):
                    continue
                new_slug = ProductModel.generate_slug(p.get("name", ""))
                if not new_slug:
                    continue
                db.table("products").update({"slug": new_slug}).eq("id", p["id"]).execute()
                fixed += 1
            return fixed
        except Exception as e:
            logger.error(f"Lỗi fix_missing_slugs: {e}")
            return 0

    @staticmethod
    def fix_missing_barcodes() -> int:
        """Backfill barcode cho các sản phẩm cũ chưa có."""
        db = ProductModel._db()
        fixed = 0
        try:
            res = db.table("products").select("id, created_at, barcode").execute()
            for p in (res.data or []):
                if p.get("barcode"):
                    continue
                # Sinh barcode dựa trên product_id và thời gian tạo thực tế
                created = p.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    prefix = f"GUA-{dt.strftime('%y%m')}"
                except Exception:
                    prefix = f"GUA-{datetime.now().strftime('%y%m')}"

                hex_part = p["id"].replace("-", "")[:6].upper()
                barcode = f"{prefix}-{hex_part}"
                db.table("products").update({"barcode": barcode}).eq("id", p["id"]).execute()
                fixed += 1
            return fixed
        except Exception as e:
            logger.error(f"Lỗi fix_missing_barcodes: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════
    #  READ (GET)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_categories(limit: int=3) -> list:
        db = ProductModel._db()
        try:
            res = db.table("categories").select("*").limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Lỗi get_categories: {e}")
            return []

    @staticmethod
    def get_featured(limit: int=8) -> list:
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
            return [ProductModel._format_product(item) for item in (res.data or [])]
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
        db = ProductModel._db()
        offset = (page - 1) * per_page
        try:
            query = db.table("products").select(
                "*, categories(name, slug), product_variants(*), product_images(*)", count="exact"
            )
            if not admin_mode:
                query = query.is_("deleted_at", "null").eq("is_active", True)

            if category_slug:
                try:
                    cat_res = db.table("categories").select("id").eq("slug", category_slug).limit(1).execute()
                    if cat_res.data:
                        query = query.eq("category_id", cat_res.data[0]["id"])
                    else:
                        return {"items": [], "total": 0, "page": page, "per_page": per_page}
                except Exception as cat_err:
                    logger.error(f"Lỗi resolve category_slug '{category_slug}': {cat_err}")

            if gender:
                query = query.eq("gender", gender)
            if keyword:
                query = query.ilike("name", f"%{keyword}%")

            res = query.order("created_at", desc=True).range(offset, offset + per_page - 1).execute()
            return {
                "items": [ProductModel._format_product(item) for item in (res.data or [])],
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

    @staticmethod
    def get_by_barcode(barcode: str):
        """Tìm sản phẩm theo mã vạch — dùng trong POS scan."""
        if not barcode:
            return None
        db = ProductModel._db()
        try:
            res = (
                db.table("products")
                .select("*, product_variants(*)")
                .eq("barcode", barcode.strip().upper())
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
            )
            return ProductModel._format_product(res.data[0]) if res.data else None
        except Exception as e:
            logger.error(f"Lỗi get_by_barcode '{barcode}': {e}")
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
            # Insert trước để lấy ID
            res = db.table("products").insert(data).execute()
            if not res.data:
                return None

            product = res.data[0]
            pid = product["id"]

            # Sinh barcode từ UUID thực tế của DB
            barcode = ProductModel.generate_barcode(pid)
            db.table("products").update({"barcode": barcode}).eq("id", pid).execute()
            product["barcode"] = barcode

            logger.info(f"[ProductModel] Tạo SP '{data.get('name')}' | barcode: {barcode}")
            return product

        except Exception as e:
            logger.error(f"Lỗi tạo sản phẩm: {e}")
            return None

    @staticmethod
    def update(pid: str, data: dict) -> bool:
        if not pid:
            return False
        if "slug" in data and not data["slug"]:
            data.pop("slug")
        # Không cho phép ghi đè barcode qua update thông thường
        data.pop("barcode", None)
        try:
            res = ProductModel._db().table("products").update(data).eq("id", pid).execute()
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
    #  IMAGES
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
                db.table("product_images").insert([
                    {"product_id": pid, "url": url, "sort_order": i, "is_primary": (i == 0)}
                    for i, url in enumerate(urls)
                ]).execute()
            return True
        except Exception as e:
            logger.error(f"Lỗi sync_images '{pid}': {e}")
            return False

    @staticmethod
    def upload_to_storage(file_bytes: bytes, filename: str, content_type: str) -> str:
        db = ProductModel._db()
        try:
            path = f"products/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            db.storage.from_("products").upload(path, file_bytes, {"content-type": content_type})
            return db.storage.from_("products").get_public_url(path)
        except Exception as e:
            logger.error(f"Lỗi upload storage: {e}")
            return ""

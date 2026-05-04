"""
app/controllers/product_controller.py
Quản lý luồng hiển thị sản phẩm Storefront. 
Tích hợp AI Visual Search và xử lý Biến thể (Variants) chuẩn E-commerce.
"""

import logging
import requests
from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for

from app.models.product_model import ProductModel
from app.models.category_model import CategoryModel
# Đã thêm import get_supabase và loại bỏ 'abort' bị thừa
from app.utils.supabase_client import get_supabase

products_bp = Blueprint("products", __name__)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  HELPERS (XÁC THỰC AI ENGINE)
# ═══════════════════════════════════════════════════════════════


def _get_ai_headers():
    """Lấy token xác thực nếu Space Hugging Face đang để chế độ Private"""
    token = current_app.config.get("HF_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}

# ═══════════════════════════════════════════════════════════════
#  STOREFRONT ROUTING (HIỂN THỊ CỬA HÀNG)
# ═══════════════════════════════════════════════════════════════


@products_bp.route("/")
def index():
    """Trang chủ – Hiển thị sản phẩm nổi bật"""
    try:
        res = ProductModel.get_all(page=1, per_page=8, admin_mode=False)
        # SỬA Ở ĐÂY: Thêm products/ vào trước
        return render_template("products/index.html", featured_products=res.get("items", []))
    except Exception as e:
        logger.error(f"Lỗi trang chủ: {e}")
        # SỬA Ở ĐÂY NỮA: Để khi có lỗi nó vẫn tìm đúng file
        return render_template("products/index.html", featured_products=[])


@products_bp.route("/shop")
def shop():
    """Trang danh sách sản phẩm (Có phân trang & Bộ lọc)"""
    # Ép kiểu dict để bypass linter PyDev không báo lỗi .get()
    args = dict(request.args)
    page = int(args.get("page", 1))
    category_slug = args.get("category")
    gender = args.get("gender")
    keyword = args.get("q")
    
    result = ProductModel.get_all(
        page=page,
        per_page=12,
        category_slug=category_slug,
        gender=gender,
        keyword=keyword,
        admin_mode=False
    )
    
    categories = CategoryModel.get_all()
    total_pages = max(1, (result["total"] + 11) // 12)
    
    return render_template(
        "products/shop.html",
        products=result["items"],
        total_pages=total_pages,
        page=page,
        categories=categories,
        current_category=category_slug,
        current_gender=gender,
        keyword=keyword
    )


@products_bp.route("/product/<slug>")
def detail(slug):
    # ── GUARD: slug không hợp lệ ──
    if not slug or slug in ("None", "null", "undefined", ""):
        flash("Đường dẫn sản phẩm không hợp lệ.", "warning")
        return redirect(url_for("products.shop"))

    product = ProductModel.get_by_slug(slug)
    
    if not product:
        flash("Sản phẩm không tồn tại hoặc đã ngừng kinh doanh.", "warning")
        return redirect(url_for("products.shop"))
        # ── DEBUG: In ra terminal để kiểm tra ──
    print("=" * 60)
    print(f"[DEBUG] slug        : {slug}")
    print(f"[DEBUG] product.id  : {product.get('id')}")
    print(f"[DEBUG] variants raw: {product.get('product_variants')}")
    print("=" * 60)
    
     # #Gom nhóm biến thể theo màu
    color_groups = {}
    variants = product.get("product_variants", []) or []
    
    for v in variants:
        c_name = v.get("color_name")
        if not c_name:
            continue
        if c_name not in color_groups:
            color_groups[c_name] = {
                "hex": v.get("color_hex") or "#1a1a1a",
                "sizes": []
            }
        price = v.get("price_override") or product.get("price") or 0
        color_groups[c_name]["sizes"].append({
            "variant_id": v["id"],
            "size": v["size"],
            "stock": v.get("stock", 0),
            "price": float(price),
        })

    # ── DEBUG: In color_groups sau khi gom ──
    print(f"[DEBUG] color_groups: {color_groups}")
    print("=" * 60)

    product["color_groups"] = color_groups

    try:
        cat_slug = (product.get("categories") or {}).get("slug")
        related_res = ProductModel.get_all(page=1, per_page=5, category_slug=cat_slug)
        related_products = [
            p for p in related_res.get("items", [])
            if p["id"] != product["id"]
        ][:4]
    except Exception:
        related_products = []

    return render_template(
        "products/detail.html",
        product=product,
        related_products=related_products
    )
# ═══════════════════════════════════════════════════════════════
#  AI VISUAL SEARCH (TÌM KIẾM BẰNG HÌNH ẢNH)
# ═══════════════════════════════════════════════════════════════


@products_bp.route("/visual-search", methods=["POST"])
def visual_search():
    """Tính năng tìm kiếm sản phẩm qua ảnh bằng AI (Hugging Face)"""
    
    # FIX: Viết kiểu kiểm tra "in" để bypass lỗi linter của PyDev đối với request.files.get
    file = request.files["image"] if "image" in request.files else None
    
    if not file or file.filename == "":
        flash("Vui lòng tải lên một hình ảnh để tìm kiếm.", "warning")
        return redirect(request.referrer or url_for("products.shop"))

    engine_url = current_app.config.get("AI_ENGINE_URL")
    if not engine_url:
        flash("Hệ thống AI chưa được cấu hình.", "danger")
        return redirect(request.referrer or url_for("products.shop"))

    try:
        # Bắn ảnh sang HF để quét Vector
        files = {'image': (file.filename, file.stream, file.mimetype)}
        response = requests.post(
            f"{engine_url}/search",
            files=files,
            headers=_get_ai_headers(),
            timeout=20  # Visual search cần nhiều thời gian xử lý hơn
        )
        
        if response.status_code == 200:
            ai_results = response.json().get("results", [])
            matched_product_ids = [item["id"] for item in ai_results if "id" in item]
            
            if matched_product_ids:
                db = get_supabase()  # Lúc này hàm đã được import chuẩn xác
                # Query lấy thông tin gốc từ DB để đảm bảo dữ liệu là Real-time
                db_res = db.table("products").select("*, categories(name, slug)").in_("id", matched_product_ids).eq("is_active", True).is_("deleted_at", "null").execute()
                matched_products = db_res.data or []
            else:
                matched_products = []
                
            flash("Đã tìm thấy các thiết kế tương tự từ kho lưu trữ.", "success")
        else:
            matched_products = []
            logger.warning(f"AI Search Error: {response.status_code} - {response.text}")
            flash("Hệ thống Matrix Vision không tìm thấy kết quả phù hợp.", "warning")

        return render_template(
            "products/shop.html",
            products=matched_products,
            keyword="Kết quả Matrix Vision",
            page=1, total_pages=1
        )
        
    except requests.exceptions.Timeout:
        logger.error("Hugging Face API Timeout (Visual Search)")
        flash("Hệ thống phân tích hình ảnh đang xử lý quá tải. Vui lòng thử lại sau.", "danger")
        return redirect(request.referrer or url_for("products.shop"))
    except Exception as e:
        logger.error(f"Lỗi Visual Search: {e}")
        flash("Lỗi kết nối đến máy chủ Matrix Vision.", "danger")
        return redirect(request.referrer or url_for("products.shop"))

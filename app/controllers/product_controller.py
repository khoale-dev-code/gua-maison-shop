"""
app/controllers/product_controller.py
Quản lý luồng hiển thị sản phẩm. Toàn bộ logic AI (Visual Search & Recommender) 
được gọi qua Microservice trên Hugging Face để tối ưu bộ nhớ cho Vercel.
"""

import logging
import requests
from flask import Blueprint, render_template, request, abort, current_app, flash, redirect, url_for

from app.services.product_service import ProductService
from app.models.product_model import ProductModel

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
#  TRANG CHỦ (STOREFRONT INDEX)
# ═══════════════════════════════════════════════════════════════

@products_bp.route("/")
def index():
    """Trang chủ – Hiển thị sản phẩm nổi bật với cơ chế fallback an toàn."""
    try:
        limit = current_app.config.get("FEATURED_PRODUCTS_LIMIT", 8)
        featured = ProductModel.get_featured(limit)
    except Exception:
        logger.exception("Sự cố khi lấy sản phẩm nổi bật tại trang Home")
        if current_app.debug: raise
        featured = []
    
    return render_template("products/index.html", featured=featured)


# ═══════════════════════════════════════════════════════════════
#  TRANG CỬA HÀNG (THE ARCHIVE / SHOP)
# ═══════════════════════════════════════════════════════════════

@products_bp.route("/shop")
def shop():
    """Trang cửa hàng – Quản lý phân trang, lọc danh mục và tìm kiếm text."""
    try:
        page = request.args.get("page", 1, type=int)
        if page < 1: page = 1
    except (ValueError, TypeError):
        page = 1

    category = request.args.get("category")
    keyword = request.args.get("q", "").strip()
    per_page = current_app.config.get("PRODUCTS_PER_PAGE", 12)

    try:
        result = ProductService.get_catalog(page, per_page, keyword, category)
        items = result.get("items", [])
        total = result.get("total", 0)
        
        total_pages = max(1, (total + per_page - 1) // per_page)
        
        if page > total_pages and total > 0:
            return redirect(url_for("products.shop", page=total_pages, category=category, q=keyword))

    except Exception:
        logger.exception(f"Lỗi Shop Layer: category={category}, keyword={keyword}")
        if current_app.debug: raise
        flash("Đã có lỗi xảy ra khi tải danh mục sản phẩm.", "danger")
        items, total, total_pages = [], 0, 1

    return render_template(
        "products/shop.html",
        products=items,
        page=page,
        total_pages=total_pages,
        keyword=keyword,
        category=category
    )


# ═══════════════════════════════════════════════════════════════
#  CHI TIẾT SẢN PHẨM & AI GỢI Ý (MICROSERVICE CALL)
# ═══════════════════════════════════════════════════════════════

@products_bp.route("/product/<uuid:product_id>")
def detail(product_id):
    """Trang chi tiết sản phẩm – Gọi API Gợi ý (Scikit-learn) từ Hugging Face."""
    product_id_str = str(product_id)
    engine_url = current_app.config.get("AI_ENGINE_URL")
    
    try:
        # 1. Lấy chi tiết sản phẩm khách đang xem
        product = ProductService.get_product_detail(product_id_str)
        if not product:
            logger.warning(f"Truy cập sản phẩm không tồn tại: ID={product_id_str}")
            abort(404)
            
        # 2. Kích hoạt AI Gợi ý sản phẩm (Microservice)
        related_products = []
        if engine_url:
            try:
                # Lấy data mẫu để gửi cho AI tính toán (Giới hạn 500 sp để tiết kiệm băng thông)
                all_products_data = ProductModel.get_all(page=1, per_page=500, admin_mode=False)
                all_products = all_products_data.get("items", [])
                
                if all_products:
                    payload = {
                        "target_id": product_id_str, 
                        "products": all_products, 
                        "limit": 4
                    }
                    # Gọi API sang Hugging Face
                    res = requests.post(
                        f"{engine_url}/recommend", 
                        json=payload, 
                        headers=_get_ai_headers(),
                        timeout=8 # Timeout 8s, nếu HF ngủ đông thì bỏ qua để khách ko bị treo web
                    )
                    
                    if res.status_code == 200:
                        related_products = res.json().get("results", [])
            except requests.exceptions.Timeout:
                logger.warning("AI Engine Recommendation Timeout (Silent Fail)")
            except Exception as ai_error:
                logger.error(f"Lỗi hệ thống AI Recommender: {ai_error}")
            
        return render_template(
            "products/detail.html", 
            product=product,
            related_products=related_products
        )
        
    except Exception as e:
        logger.exception(f"Lỗi truy vấn chi tiết sản phẩm: ID={product_id_str}")
        abort(500)


# ═══════════════════════════════════════════════════════════════
#  TÌM KIẾM BẰNG HÌNH ẢNH (VISUAL SEARCH MICROSERVICE)
# ═══════════════════════════════════════════════════════════════

@products_bp.route("/visual-search", methods=["POST"])
def visual_search():
    """Nhận ảnh từ User, gửi qua AI Engine (CLIP + FAISS) để quét thiết kế tương tự."""
    engine_url = current_app.config.get("AI_ENGINE_URL")
    
    if not engine_url:
        flash("Hệ thống Matrix Vision chưa được kích hoạt.", "warning")
        return redirect(request.referrer or url_for("products.shop"))

    if 'image' not in request.files:
        flash("Vui lòng cung cấp một bức ảnh để phân tích.", "danger")
        return redirect(request.referrer or url_for("products.shop"))

    file = request.files['image']
    if file.filename == '':
        return redirect(request.referrer or url_for("products.shop"))

    try:
        # Bước 1: Lazy Sync (Đồng bộ kho đồ). 
        # Cập nhật Vector nếu có sản phẩm mới trước khi quét ảnh.
        try:
            all_products = ProductModel.get_all(admin_mode=False).get("items", [])
            requests.post(
                f"{engine_url}/build-index", 
                json={"products": all_products}, 
                headers=_get_ai_headers(), 
                timeout=5
            )
        except Exception as sync_err:
            logger.warning(f"Lazy Sync Failed (Có thể đã sync trước đó): {sync_err}")

        # Bước 2: Bắn ảnh sang HF để quét Vector
        files = {'image': (file.filename, file.stream, file.mimetype)}
        response = requests.post(
            f"{engine_url}/search", 
            files=files, 
            headers=_get_ai_headers(), 
            timeout=20 # Visual search cần nhiều thời gian xử lý hơn
        )
        
        if response.status_code == 200:
            matched_products = response.json().get("results", [])
            flash("Đã tìm thấy các thiết kế tương tự từ kho lưu trữ.", "success")
        else:
            matched_products = []
            logger.warning(f"AI Search Error: {response.status_code} - {response.text}")
            flash("Hệ thống Matrix Vision không tìm thấy kết quả phù hợp.", "warning")

        # Trả về trang Shop kèm theo kết quả
        return render_template(
            "products/shop.html", 
            products=matched_products,
            keyword="Matrix Vision Results",
            category=None,
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
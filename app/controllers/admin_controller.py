"""
app/controllers/admin_controller.py
Quản trị hệ thống, sản phẩm, đơn hàng, danh mục và Báo cáo dữ liệu (Analytics).
"""

import re
import logging
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models.product_model import ProductModel
from app.models.category_model import CategoryModel
from app.models.order_model import OrderModel
from app.utils.supabase_client import get_supabase
from app.middleware.auth_required import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Khởi tạo logger để ghi Audit Log
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  HELPERS & AI ENGINE CONFIG
# ═══════════════════════════════════════════════════════════════

def _get_clean_form():
    """Helper giúp IDE nhận diện request.form là dictionary."""
    return request.form

def _get_clean_args():
    """Helper giúp IDE nhận diện request.args là dictionary."""
    return request.args

def _get_ai_headers():
    """Tạo header xác thực linh hoạt cho Hugging Face AI Engine"""
    token = current_app.config.get("HF_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/")
@admin_required
def dashboard():
    try:
        stats = OrderModel.get_stats()
        user_count = OrderModel.get_user_count()
        # AdminMode lấy cả sp ẩn
        prod_data = ProductModel.get_all(page=1, per_page=1, admin_mode=True)
        prod_count = prod_data.get("total", 0)
        cat_data = ProductModel.count_by_category()
        
        return render_template("admin/dashboard.html",
            stats=stats, user_count=user_count,
            prod_count=prod_count, cat_data=cat_data)
    except Exception:
        logger.exception("Dashboard loading failed")
        return render_template("errors/500.html"), 500


# ═══════════════════════════════════════════════════════════════
#  PRODUCTS
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/products")
@admin_required
def products():
    args = _get_clean_args()
    try:
        page = int(args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
        
    keyword = args.get("q", "").strip()
    per_page = current_app.config.get("ADMIN_PRODUCTS_PER_PAGE", 15)

    try:
        result = ProductModel.get_all(page=page, per_page=per_page, keyword=keyword, admin_mode=True)
        total_pages = max(1, (result["total"] + per_page - 1) // per_page)
        
        return render_template("admin/products.html",
            products=result["items"], total=result["total"],
            page=page, total_pages=total_pages, keyword=keyword,
            cats=CategoryModel.get_all())
    except Exception:
        logger.exception("Admin Products list failed")
        flash("Lỗi tải danh sách sản phẩm.", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    cats = CategoryModel.get_all()
    if request.method == "POST":
        form = _get_clean_form()
        
        name = form.get("name", "").strip()
        price = form.get("price", 0)
        stock = form.get("stock", 0)
        
        if not name:
            flash("Tên sản phẩm không được để trống.", "danger")
            return render_template("admin/product_form.html", product=None, cats=cats)

        try:
            data = {
                "name": name,
                "description": form.get("description", ""),
                "price": float(price),
                "stock": int(stock),
                "category_id": form.get("category_id") or None,
                "thumbnail_url": form.get("thumbnail_url", "").strip() or None,
                "is_featured": "is_featured" in form,
                "is_active": "is_active" in form
            }
            prod = ProductModel.create(data)
            if prod:
                logger.info(f"Audit: Product created {prod.get('id')}")
                flash(f"✅ Đã thêm: {name}", "success")
                return redirect(url_for("admin.products"))
        except Exception:
            logger.exception("Add product fail")
            flash("Lỗi hệ thống khi thêm sản phẩm.", "danger")

    return render_template("admin/product_form.html", product=None, cats=cats)


@admin_bp.route("/products/edit/<pid>", methods=["GET", "POST"])
@admin_required
def edit_product(pid):
    try:
        product = ProductModel.get_by_id(pid)
        cats = CategoryModel.get_all()
        if not product:
            flash("Sản phẩm không tồn tại.", "danger")
            return redirect(url_for("admin.products"))

        if request.method == "POST":
            form = _get_clean_form()
            
            data = {
                "name": form.get("name", "").strip(),
                "price": float(form.get("price", 0)),
                "stock": int(form.get("stock", 0)),
                "is_active": "is_active" in form,
                "is_featured": "is_featured" in form,
                "category_id": form.get("category_id") or None,
                "thumbnail_url": form.get("thumbnail_url", "").strip() or None
            }
            
            if ProductModel.update(pid, data):
                logger.info(f"Audit: Product updated {pid}")
                flash("✅ Cập nhật thành công!", "success")
                return redirect(url_for("admin.products"))
            
        return render_template("admin/product_form.html", product=product, cats=cats)
    except Exception:
        logger.exception(f"Edit product fail: {pid}")
        flash("Lỗi xử lý yêu cầu.", "danger")
        return redirect(url_for("admin.products"))


# ═══════════════════════════════════════════════════════════════
#  CATEGORIES 
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/categories")
@admin_required
def categories():
    try:
        cats = CategoryModel.get_all()
        return render_template("admin/categories.html", cats=cats)
    except Exception as e:
        logger.exception(f"Lỗi tải danh mục: {e}")
        flash("Hệ thống đang bận, không thể tải danh mục.", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/categories/add", methods=["POST"])
@admin_required
def add_category():
    form = _get_clean_form()
    name = form.get("name", "").strip()
    slug = form.get("slug", "").strip()
    
    if not name or not slug:
        flash("Vui lòng điền đầy đủ tên và slug danh mục.", "danger")
    else:
        try:
            CategoryModel.create({"name": name, "slug": slug})
            flash(f"Đã thêm phân khu: {name}", "success")
        except Exception as e:
            logger.error(f"Lỗi thêm danh mục: {e}")
            flash("Có lỗi xảy ra khi thêm danh mục.", "danger")
            
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/edit/<cat_id>", methods=["GET", "POST"])
@admin_required
def edit_category(cat_id):
    try:
        cats = CategoryModel.get_all()
        cat = next((c for c in cats if str(c['id']) == str(cat_id)), None)
        if not cat:
            flash("Không tìm thấy phân khu.", "danger")
            return redirect(url_for("admin.categories"))
            
        if request.method == "POST":
            form = _get_clean_form()
            db = get_supabase()
            db.table("categories").update({
                "name": form.get("name", "").strip(),
                "slug": form.get("slug", "").strip()
            }).eq("id", cat_id).execute()
            
            flash("Đã cập nhật phân khu thành công.", "success")
            return redirect(url_for("admin.categories"))
            
        return render_template("admin/category_edit.html", cat=cat)
    except Exception as e:
        logger.error(f"Lỗi sửa danh mục {cat_id}: {e}")
        return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/delete/<cat_id>", methods=["POST"])
@admin_required
def delete_category(cat_id):
    try:
        db = get_supabase()
        db.table("categories").delete().eq("id", cat_id).execute()
        flash("Đã xóa phân khu an toàn.", "success")
    except Exception as e:
        logger.error(f"Lỗi xóa danh mục {cat_id}: {e}")
        flash("Không thể xóa phân khu lúc này (Có thể do còn sản phẩm liên kết).", "danger")
    return redirect(url_for("admin.categories"))


# ═══════════════════════════════════════════════════════════════
#  ORDERS 
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/orders")
@admin_required
def orders():
    args = _get_clean_args()
    try:
        page = int(args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
        
    status_filter = args.get("status", "").strip()
    per_page = 20

    try:
        result = OrderModel.get_all(page=page, per_page=per_page, status=status_filter) if hasattr(OrderModel, 'get_all') else {"items": [], "total": 0}
        total_pages = max(1, (result["total"] + per_page - 1) // per_page)
        
        return render_template("admin/orders.html",
            orders=result["items"], total=result["total"],
            page=page, total_pages=total_pages, current_status=status_filter)
    except Exception as e:
        logger.exception(f"Lỗi tải danh sách đơn hàng: {e}")
        flash("Lỗi tải danh sách đơn hàng.", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/orders/<order_id>")
@admin_required
def order_detail(order_id):
    try:
        order = OrderModel.get_by_id(order_id)
        if not order:
            flash("Đơn hàng không tồn tại.", "danger")
            return redirect(url_for("admin.orders"))
        return render_template("admin/order_detail.html", order=order)
    except Exception as e:
        logger.exception(f"Lỗi tải chi tiết đơn hàng {order_id}: {e}")
        flash("Không thể tải chi tiết đơn hàng.", "danger")
        return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    form = _get_clean_form()
    status = form.get("status")
    
    try:
        if OrderModel.update_status(order_id, status):
            logger.info(f"Audit: Order {order_id} status -> {status}")
            flash(f"✅ Đã chuyển trạng thái sang: {status.upper()}", "success")
        else:
            flash("Cập nhật thất bại.", "danger")
    except Exception:
        logger.exception(f"Order status fail: {order_id}")
        flash("Lỗi hệ thống.", "danger")

    return redirect(form.get("next") or url_for("admin.orders"))


# ═══════════════════════════════════════════════════════════════
#  BÁO CÁO PHÂN TÍCH DỮ LIỆU (MICROSERVICE PANDAS)
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/reports")
@admin_required
def reports():
    """Trang Báo Cáo Phân Tích (Kéo dữ liệu thô gửi sang Hugging Face xử lý)"""
    db = get_supabase()
    engine_url = current_app.config.get("AI_ENGINE_URL")
    
    # Nếu chưa config AI_ENGINE_URL, báo lỗi ngay để admin biết
    if not engine_url:
        flash("Chưa cấu hình AI_ENGINE_URL. Vui lòng kiểm tra biến môi trường.", "warning")
        return render_template("admin/reports.html", report={"top_products": [], "daily_revenue": []})

    try:
        # Lấy dữ liệu Đơn hàng & Chi tiết (Bỏ qua đơn đã hủy)
        # LƯU Ý: Cú pháp query lồng nhau (order_items -> products) của Supabase
        res = db.table("orders").select("""
            created_at, 
            status, 
            order_items(
                quantity, 
                unit_price, 
                products(name)
            )
        """).neq("status", "cancelled").execute()
        
        # Flatten (trải phẳng) dữ liệu chuẩn bị gửi đi cho Pandas
        sales_data = []
        for order in res.data:
            date_str = order.get("created_at", "")[:10] 
            
            # Xử lý các order_items bên trong đơn hàng
            for item in order.get("order_items", []):
                prod_node = item.get("products")
                # Trong quan hệ 1-nhiều, Supabase trả về dict nếu là 1 object, list nếu là mảng
                if isinstance(prod_node, dict):
                    prod_name = prod_node.get("name", "Unknown Item")
                elif isinstance(prod_node, list) and len(prod_node) > 0:
                    prod_name = prod_node[0].get("name", "Unknown Item")
                else:
                    prod_name = "Unknown Item"
                
                qty = item.get("quantity", 0)
                price = item.get("unit_price", 0)
                
                sales_data.append({
                    "date": date_str,
                    "product_name": prod_name,
                    "qty": qty,
                    "revenue": qty * price
                })

        # Gửi dữ liệu thô sang Hugging Face để AI Pandas xử lý
        ai_res = requests.post(
            f"{engine_url}/analyze-sales", 
            json={"sales": sales_data}, 
            headers=_get_ai_headers(),
            timeout=20  # Tăng timeout cho việc phân tích dữ liệu lớn
        )
        
        report_data = {"top_products": [], "daily_revenue": []}
        if ai_res.status_code == 200:
            report_data = ai_res.json()
        else:
            logger.error(f"Hugging Face API Error: {ai_res.status_code} - {ai_res.text}")
            flash("Lỗi xử lý từ máy chủ AI Pandas.", "danger")

        return render_template("admin/reports.html", report=report_data)

    except requests.exceptions.Timeout:
        logger.error("Timeout khi gọi API Pandas trên Hugging Face")
        flash("Máy chủ phân tích dữ liệu đang quá tải hoặc chưa khởi động. Vui lòng thử lại sau 1 phút.", "danger")
        return redirect(url_for("admin.dashboard"))
    except Exception as e:
        logger.error(f"Lỗi truy xuất Report: {e}")
        flash("Lỗi kết nối hoặc xử lý truy vấn dữ liệu.", "danger")
        return redirect(url_for("admin.dashboard")) 
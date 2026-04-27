"""
app/controllers/admin_controller.py
Quản trị hệ thống, sản phẩm (kèm multi-image), đơn hàng, danh mục và báo cáo.
"""

import re
import uuid
import logging
import requests
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app, jsonify
)
from app.models.product_model import ProductModel
from app.models.category_model import CategoryModel
from app.models.order_model import OrderModel
from app.utils.supabase_client import get_supabase
from app.middleware.auth_required import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════


def _get_clean_form():
    return request.form


def _get_clean_args():
    return request.args


def _get_ai_headers():
    token = current_app.config.get("HF_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _allowed_file(filename: str) -> bool:
    """Kiểm tra đuôi file có nằm trong whitelist."""
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def _extract_image_urls(form) -> list[str]:
    """
    Lấy danh sách URL ảnh từ form (getlist hỗ trợ nhiều input cùng name).
    Lọc bỏ chuỗi rỗng, trùng lặp, và giữ nguyên thứ tự.
    """
    seen = set()
    result = []
    for url in form.getlist("image_urls"):
        url = url.strip()
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result

# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/")
@admin_required
def dashboard():
    try:
        stats = OrderModel.get_stats()
        user_count = OrderModel.get_user_count()
        prod_data = ProductModel.get_all(page=1, per_page=1, admin_mode=True)
        prod_count = prod_data.get("total", 0)
        cat_data = ProductModel.count_by_category()

        return render_template(
            "admin/dashboard.html",
            stats=stats, user_count=user_count,
            prod_count=prod_count, cat_data=cat_data,
        )
    except Exception:
        logger.exception("Dashboard loading failed")
        return render_template("errors/500.html"), 500

# ═══════════════════════════════════════════════════════════════
#  PRODUCTS — DANH SÁCH
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/products")
@admin_required
def products():
    args = _get_clean_args()
    try:
        page = max(1, int(args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    keyword = args.get("q", "").strip()
    per_page = current_app.config.get("ADMIN_PRODUCTS_PER_PAGE", 15)

    try:
        result = ProductModel.get_all(page=page, per_page=per_page, keyword=keyword, admin_mode=True)
        total_pages = max(1, (result["total"] + per_page - 1) // per_page)

        return render_template(
            "admin/products.html",
            products=result["items"], total=result["total"],
            page=page, total_pages=total_pages, keyword=keyword,
            cats=CategoryModel.get_all(),
        )
    except Exception:
        logger.exception("Admin Products list failed")
        flash("Lỗi tải danh sách sản phẩm.", "danger")
        return redirect(url_for("admin.dashboard"))

# ═══════════════════════════════════════════════════════════════
#  PRODUCTS — THÊM MỚI
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    cats = CategoryModel.get_all()

    if request.method == "POST":
        form = _get_clean_form()
        name = form.get("name", "").strip()

        if not name:
            flash("Tên sản phẩm không được để trống.", "danger")
            return render_template("admin/product_form.html", product=None, cats=cats)

        try:
            # 1. Tạo bản ghi sản phẩm
            data = {
                "name": name,
                "description": form.get("description", ""),
                "price": float(form.get("price", 0)),
                "stock": int(form.get("stock", 0)),
                "category_id": form.get("category_id") or None,
                "thumbnail_url": form.get("thumbnail_url", "").strip() or None,
                "is_featured": "is_featured" in form,
                "is_active": "is_active" in form,
            }
            prod = ProductModel.create(data)
            if not prod:
                raise RuntimeError("ProductModel.create trả về rỗng")

            pid = prod["id"]

            # 2. Xử lý ảnh: ưu tiên file upload, sau đó URL nhập tay
            _handle_images_on_save(pid, form, request.files)

            logger.info(f"Audit: Product created id={pid}")
            flash(f"Đã thêm sản phẩm: {name}", "success")
            return redirect(url_for("admin.products"))

        except Exception:
            logger.exception("Add product failed")
            flash("Lỗi hệ thống khi thêm sản phẩm.", "danger")

    return render_template("admin/product_form.html", product=None, cats=cats)

# ═══════════════════════════════════════════════════════════════
#  PRODUCTS — CHỈNH SỬA
# ═══════════════════════════════════════════════════════════════


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
                "description": form.get("description", ""),
                "price": float(form.get("price", 0)),
                "stock": int(form.get("stock", 0)),
                "is_active": "is_active" in form,
                "is_featured": "is_featured" in form,
                "category_id": form.get("category_id") or None,
                "thumbnail_url": form.get("thumbnail_url", "").strip() or None,
            }

            if ProductModel.update(pid, data):
                # Đồng bộ lại toàn bộ ảnh
                _handle_images_on_save(pid, form, request.files)

                logger.info(f"Audit: Product updated id={pid}")
                flash("Cập nhật thành công!", "success")
                return redirect(url_for("admin.products"))

        # Tải ảnh hiện tại để hiển thị trên form
        product["images"] = ProductModel.get_images(pid)
        return render_template("admin/product_form.html", product=product, cats=cats)

    except Exception:
        logger.exception(f"Edit product failed. ID={pid}")
        flash("Lỗi xử lý yêu cầu.", "danger")
        return redirect(url_for("admin.products"))

# ═══════════════════════════════════════════════════════════════
#  PRODUCTS — TOGGLE / DELETE
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/products/toggle/<pid>", methods=["POST"])
@admin_required
def toggle_product(pid):
    try:
        product = ProductModel.get_by_id(pid)
        if product:
            new_state = not product.get("is_active", True)
            ProductModel.update(pid, {"is_active": new_state})
            label = "Hiển thị" if new_state else "Ẩn"
            flash(f"Đã {label} sản phẩm.", "success")
    except Exception:
        logger.exception(f"Toggle product failed. ID={pid}")
        flash("Lỗi hệ thống.", "danger")

    return redirect(url_for("admin.products"))


@admin_bp.route("/products/delete/<pid>", methods=["POST"])
@admin_required
def delete_product(pid):
    try:
        if ProductModel.delete(pid):
            flash("Đã xóa sản phẩm.", "success")
        else:
            flash("Không tìm thấy sản phẩm.", "danger")
    except Exception:
        logger.exception(f"Delete product failed. ID={pid}")
        flash("Lỗi hệ thống.", "danger")

    return redirect(url_for("admin.products"))

# ═══════════════════════════════════════════════════════════════
#  IMAGES — API ENDPOINTS (AJAX)
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/products/<pid>/images/upload", methods=["POST"])
@admin_required
def upload_image(pid):
    """
    AJAX endpoint: nhận file upload → lưu Storage → trả về URL + image_id.
    Hỗ trợ upload nhiều file cùng lúc (input multiple).
    """
    files = request.files.getlist("files")
    results = []

    for file in files:
        if not file or not file.filename or not _allowed_file(file.filename):
            continue
        try:
            file_bytes = file.read()
            content_type = file.content_type or "image/jpeg"
            public_url = ProductModel.upload_to_storage(file_bytes, file.filename, content_type)

            if public_url:
                # Lấy sort_order tiếp theo
                existing = ProductModel.get_images(pid)
                next_order = len(existing)
                img = ProductModel.add_image(
                    pid, public_url,
                    is_primary=(next_order == 0),
                    sort_order=next_order,
                )
                results.append({"id": img.get("id"), "url": public_url})
            else:
                logger.warning(f"upload_to_storage trả về None. File={file.filename}")
        except Exception:
            logger.exception(f"Upload image failed. Product={pid}, File={file.filename}")

    if results:
        return jsonify({"success": True, "images": results})
    return jsonify({"success": False, "message": "Không upload được ảnh."}), 400


@admin_bp.route("/products/<pid>/images/<image_id>/delete", methods=["POST"])
@admin_required
def delete_image(pid, image_id):
    """AJAX endpoint: xóa 1 ảnh theo image_id."""
    try:
        ok = ProductModel.delete_image(image_id)
        return jsonify({"success": ok})
    except Exception:
        logger.exception(f"Delete image failed. Image={image_id}")
        return jsonify({"success": False}), 500


@admin_bp.route("/products/<pid>/images/<image_id>/set-primary", methods=["POST"])
@admin_required
def set_primary_image(pid, image_id):
    """AJAX endpoint: đặt ảnh làm ảnh chính."""
    try:
        ok = ProductModel.set_primary_image(image_id, pid)
        return jsonify({"success": ok})
    except Exception:
        logger.exception(f"Set primary failed. Image={image_id}")
        return jsonify({"success": False}), 500


@admin_bp.route("/products/<pid>/images/reorder", methods=["POST"])
@admin_required
def reorder_images(pid):
    """AJAX endpoint: cập nhật thứ tự ảnh. Body: [{"id": "...", "sort_order": 0}, ...]"""
    try:
        data = request.get_json(force=True) or []
        ok = ProductModel.reorder_images(data)
        return jsonify({"success": ok})
    except Exception:
        logger.exception(f"Reorder images failed. Product={pid}")
        return jsonify({"success": False}), 500

# ═══════════════════════════════════════════════════════════════
#  CATEGORIES
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/categories")
@admin_required
def categories():
    try:
        cats = CategoryModel.get_all()
        return render_template("admin/categories.html", cats=cats)
    except Exception:
        logger.exception("Categories load failed")
        flash("Không thể tải danh mục.", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/categories/add", methods=["POST"])
@admin_required
def add_category():
    form = _get_clean_form()
    name = form.get("name", "").strip()
    slug = form.get("slug", "").strip()

    if not name or not slug:
        flash("Vui lòng điền đầy đủ tên và slug danh mục.", "danger")
    elif not SLUG_RE.match(slug):
        flash("Slug chỉ được chứa chữ thường, số và dấu gạch ngang.", "danger")
    else:
        try:
            CategoryModel.create({"name": name, "slug": slug})
            flash(f"Đã thêm danh mục: {name}", "success")
        except Exception:
            logger.exception("Add category failed")
            flash("Lỗi khi thêm danh mục.", "danger")

    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/delete/<cat_id>", methods=["POST"])
@admin_required
def delete_category(cat_id):
    try:
        get_supabase().table("categories").delete().eq("id", cat_id).execute()
        flash("Đã xóa danh mục.", "success")
    except Exception:
        logger.exception(f"Delete category failed. ID={cat_id}")
        flash("Lỗi khi xóa danh mục.", "danger")

    return redirect(url_for("admin.categories"))

# ═══════════════════════════════════════════════════════════════
#  ORDERS
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/orders")
@admin_required
def orders():
    args = _get_clean_args()
    try:
        page = max(1, int(args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = current_app.config.get("ADMIN_ORDERS_PER_PAGE", 20)

    try:
        result = OrderModel.get_all(page=page, per_page=per_page)
        total_pages = max(1, (result["total"] + per_page - 1) // per_page)

        return render_template(
            "admin/orders.html",
            orders=result["items"], total=result["total"],
            page=page, total_pages=total_pages,
        )
    except Exception:
        logger.exception("Admin Orders list failed")
        flash("Lỗi tải danh sách đơn hàng.", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/orders/<order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    form = _get_clean_form()
    status = form.get("status")

    try:
        if OrderModel.update_status(order_id, status):
            logger.info(f"Audit: Order {order_id} status → {status}")
            flash(f"Đã chuyển trạng thái: {status.upper()}", "success")
        else:
            flash("Cập nhật thất bại.", "danger")
    except Exception:
        logger.exception(f"Order status update failed. ID={order_id}")
        flash("Lỗi hệ thống.", "danger")

    return redirect(form.get("next") or url_for("admin.orders"))

# ═══════════════════════════════════════════════════════════════
#  BÁO CÁO PHÂN TÍCH (MICROSERVICE PANDAS)
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/reports")
@admin_required
def reports():
    db = get_supabase()
    engine_url = current_app.config.get("AI_ENGINE_URL")

    if not engine_url:
        flash("Chưa cấu hình AI_ENGINE_URL.", "warning")
        return render_template("admin/reports.html", report={"top_products": [], "daily_revenue": []})

    try:
        res = db.table("orders").select("""
            created_at, status,
            order_items(quantity, unit_price, products(name))
        """).neq("status", "cancelled").execute()

        sales_data = []
        for order in res.data:
            date_str = order.get("created_at", "")[:10]
            for item in order.get("order_items", []):
                prod_node = item.get("products")
                if isinstance(prod_node, dict):
                    prod_name = prod_node.get("name", "Unknown")
                elif isinstance(prod_node, list) and prod_node:
                    prod_name = prod_node[0].get("name", "Unknown")
                else:
                    prod_name = "Unknown"

                qty = item.get("quantity", 0)
                price = item.get("unit_price", 0)
                sales_data.append({"date": date_str, "product_name": prod_name,
                                   "qty": qty, "revenue": qty * price})

        ai_res = requests.post(f"{engine_url}/analyze-sales",
                                    json={"sales": sales_data},
                                    headers=_get_ai_headers(), timeout=20)
        report_data = {"top_products": [], "daily_revenue": []}

        if ai_res.status_code == 200:
            report_data = ai_res.json()
        else:
            logger.error(f"HF API Error: {ai_res.status_code}")
            flash("Lỗi xử lý từ máy chủ AI.", "danger")

        return render_template("admin/reports.html", report=report_data)

    except requests.exceptions.Timeout:
        flash("Máy chủ phân tích đang quá tải. Thử lại sau.", "danger")
        return redirect(url_for("admin.dashboard"))
    except Exception:
        logger.exception("Reports failed")
        flash("Lỗi kết nối báo cáo.", "danger")
        return redirect(url_for("admin.dashboard"))

# ═══════════════════════════════════════════════════════════════
#  PRIVATE — XỬ LÝ ẢNH KHI LƯU FORM (URL + FILE UPLOAD)
# ═══════════════════════════════════════════════════════════════


def _handle_images_on_save(pid: str, form, files) -> None:
    """
    Xử lý ảnh khi tạo / cập nhật sản phẩm:
    1. Upload các file mới lên Storage, lấy URL.
    2. Gộp URL từ file upload + URL nhập tay thành 1 danh sách.
    3. Gọi sync_images để đồng bộ DB.
    """
    uploaded_urls: list[str] = []

    # Bước 1: Xử lý file upload (input name="image_files")
    file_list = files.getlist("image_files")
    for file in file_list:
        if not file or not file.filename or not _allowed_file(file.filename):
            continue
        try:
            file_bytes = file.read()
            public_url = ProductModel.upload_to_storage(
                file_bytes, file.filename, file.content_type or "image/jpeg"
            )
            if public_url:
                uploaded_urls.append(public_url)
        except Exception:
            logger.exception(f"File upload failed trong _handle_images_on_save. File={file.filename}")

    # Bước 2: URL nhập tay (input name="image_urls")
    manual_urls = _extract_image_urls(form)

    # Bước 3: Gộp (file upload trước, URL nhập tay sau), loại trùng
    all_urls: list[str] = []
    seen: set[str] = set()
    for url in uploaded_urls + manual_urls:
        if url and url not in seen:
            seen.add(url)
            all_urls.append(url)

    # Bước 4: Đồng bộ DB (chỉ sync nếu có ảnh hoặc đang edit để xóa ảnh cũ)
    if all_urls or form.get("_images_synced"):
        ProductModel.sync_images(pid, all_urls)

        # Cập nhật thumbnail_url theo ảnh primary (hoặc ảnh đầu tiên)
        if all_urls:
            images = ProductModel.get_images(pid)
            primary = next((img for img in images if img.get("is_primary")), None)
            thumb = (primary or (images[0] if images else None))
            if thumb:
                ProductModel.update(pid, {"thumbnail_url": thumb["url"]})

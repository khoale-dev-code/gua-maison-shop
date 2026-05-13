"""
app/controllers/admin/settings.py
Controller xử lý trang Cài đặt Hệ thống.
Sections: General, Storefront, Integrations, Shipping Rules, Language.
Hỗ trợ upload ảnh/video cho storefront (hero banner, desktop banner).
"""
import logging
import uuid
from flask import request, render_template, jsonify, current_app
from ._blueprint import admin_bp
from app.models.setting_model import SettingModel
from app.services.audit_service import AuditService
from app.middleware.auth_required import admin_required
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Danh sách sections được phép cập nhật qua route này
VALID_SETTINGS_SECTIONS = [
    "general",
    "storefront",
    "integrations",
    "shipping_rules",
    "language",
]

# Cấu hình upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'avi'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ═══════════════════════════════════════════════════════════════
#  1. HIỂN THỊ GIAO DIỆN CÀI ĐẶT
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/settings", methods=["GET"])
@admin_required
def settings_page():
    """Hiển thị giao diện cài đặt hệ thống với các Tab."""
    try:
        settings = SettingModel.get_settings()

        return render_template(
            "admin/settings/index.html",
            general=settings.get("general", {}),
            storefront=settings.get("storefront", {}),
            integrations=settings.get("integrations", {}),
            shipping_rules=settings.get("shipping_rules", {}),
            language=settings.get("language", {}),
        )
    except Exception as e:
        logger.error(f"[Settings Controller] Lỗi tải trang cài đặt: {e}")
        return jsonify({"error": "Lỗi hệ thống", "detail": str(e)}), 500

# ═══════════════════════════════════════════════════════════════
#  2. CẬP NHẬT DỮ LIỆU BẰNG AJAX
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/settings/update/<section>", methods=["POST"])
@admin_required
def update_settings(section):
    if section not in VALID_SETTINGS_SECTIONS:
        return jsonify({
            "success": False,
            "message": f"Khu vực cấu hình '{section}' không hợp lệ."
        }), 400

    data = request.get_json(silent=True)
    if data is None:
        data = dict(request.form)

    if not data and section != "shipping_rules":
        return jsonify({"success": False, "message": "Không có dữ liệu nào được gửi lên."}), 400

    old_settings = SettingModel.get_section(section)
    success = SettingModel.update_section(section, data)

    if success:
        AuditService.log(
            action="UPDATE",
            table_name="system_settings",
            record_id=section,
            old_values=old_settings,
            new_values=data
        )

        section_names = {
            "general": "Thông tin chung",
            "storefront": "Giao diện cửa hàng",
            "integrations": "Khóa API & Tích hợp",
            "shipping_rules": "Luật vận chuyển",
            "language": "Ngôn ngữ Admin",
        }
        friendly_name = section_names.get(section, section.upper())

        return jsonify({
            "success": True,
            "message": f"Đã lưu thành công: {friendly_name}!"
        })

    return jsonify({"success": False, "message": "Có lỗi xảy ra khi lưu vào Database."}), 500

# ═══════════════════════════════════════════════════════════════
#  3. UPLOAD ẢNH/VIDEO CHO STOREFRONT
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/settings/upload", methods=["POST"])
@admin_required
def upload_storefront_media():
    """
    Upload file (ảnh/video) lên bucket 'storefront' trong Supabase Storage,
    trả về URL công khai để lưu vào settings.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Không có file nào được gửi lên"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Chưa chọn file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Định dạng file không được hỗ trợ. Chỉ chấp nhận: jpg, png, webp, mp4, mov."}), 400

    # Kiểm tra kích thước
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({"success": False, "error": f"File quá lớn (tối đa {MAX_FILE_SIZE // (1024*1024)}MB)"}), 400

    try:
        db = get_supabase()
        # Tạo tên file an toàn
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file_bytes = file.read()

        # Đảm bảo bucket 'storefront' tồn tại (public)
        bucket_name = "storefront"
        try:
            # Thử lấy bucket, nếu lỗi thì tạo mới
            db.storage.get_bucket(bucket_name)
        except Exception:
            # Tạo bucket public
            db.storage.create_bucket(bucket_name, {"public": True})
            logger.info(f"[Upload] Đã tạo bucket '{bucket_name}'")

        # Upload file
        db.storage.from_(bucket_name).upload(
            filename,
            file_bytes,
            {"content-type": file.mimetype}
        )
        # Lấy public URL
        public_url = db.storage.from_(bucket_name).get_public_url(filename)

        return jsonify({"success": True, "url": public_url})

    except Exception as e:
        logger.error(f"[Upload] Lỗi upload file: {e}")
        return jsonify({"success": False, "error": "Lỗi server khi upload file. Vui lòng thử lại."}), 500

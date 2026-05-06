"""
app/controllers/admin/settings.py
Controller xử lý trang Cài đặt Hệ thống (General, Storefront, API, Shipping Rules).
"""
import logging
from flask import request, render_template, jsonify
from ._blueprint import admin_bp 
from app.models.setting_model import SettingModel
from app.services.audit_service import AuditService
from app.middleware.auth_required import admin_required 

logger = logging.getLogger(__name__)

# Danh sách các khu vực được phép cập nhật (Tránh Hacker gửi field lạ)
VALID_SETTINGS_SECTIONS = ["general", "storefront", "integrations", "shipping_rules"]

# ═══════════════════════════════════════════════════════════════
#  1. HIỂN THỊ GIAO DIỆN CÀI ĐẶT
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/settings", methods=["GET"])
@admin_required 
def settings_page():
    """Hiển thị giao diện cài đặt hệ thống với 4 Tab"""
    try:
        # Lấy cấu hình toàn cục từ Model (Đã được cache tối ưu)
        settings = SettingModel.get_settings()
        
        return render_template(
            "admin/settings/index.html",
            general=settings.get("general", {}),
            storefront=settings.get("storefront", {}),
            integrations=settings.get("integrations", {}),
            shipping_rules=settings.get("shipping_rules", {})
        )
    except Exception as e:
        logger.error(f"[Settings Controller] Lỗi tải trang cài đặt: {e}")
        return render_template("admin/errors/500.html"), 500

# ═══════════════════════════════════════════════════════════════
#  2. CẬP NHẬT DỮ LIỆU BẰNG AJAX
# ═══════════════════════════════════════════════════════════════


@admin_bp.route("/settings/update/<section>", methods=["POST"])
@admin_required 
def update_settings(section):
    """
    Nhận dữ liệu từ Frontend và cập nhật vào Database theo từng tab.
    Cập nhật thành công sẽ tự động ghi log vào Audit_Logs.
    """
    # 1. Bảo mật: Chặn các request cập nhật khu vực không tồn tại
    if section not in VALID_SETTINGS_SECTIONS:
        return jsonify({"success": False, "message": f"Khu vực cấu hình '{section}' không hợp lệ."}), 400

    # 2. Lấy dữ liệu gửi lên (Hỗ trợ cả JSON Payload và Form Data)
    data = request.get_json(silent=True)
    if data is None:
        data = dict(request.form)
        
    if not data and section != "shipping_rules":
        return jsonify({"success": False, "message": "Không có dữ liệu nào được gửi lên."}), 400

    # 3. Lấy dữ liệu cũ để lưu Log so sánh (Audit Log)
    old_settings = SettingModel.get_section(section)

    # 4. Ghi dữ liệu mới vào DB qua Model
    success = SettingModel.update_section(section, data)
    
    if success:
        # Ghi vết hành động của Admin vào hệ thống
        AuditService.log(
            action="UPDATE",
            table_name="system_settings",
            record_id=section,  # Lưu tên Tab để dễ tìm kiếm
            old_values=old_settings,
            new_values=data
        )
        
        # Format lại tên cho thân thiện khi thông báo
        section_names = {
            "general": "Thông tin chung",
            "storefront": "Giao diện cửa hàng",
            "integrations": "Khóa API & Tích hợp",
            "shipping_rules": "Luật vận chuyển & Cảnh báo"
        }
        friendly_name = section_names.get(section, section.upper())
        
        return jsonify({"success": True, "message": f"Đã lưu thành công cấu hình {friendly_name}!"})
    
    return jsonify({"success": False, "message": "Có lỗi xảy ra khi lưu vào Database."}), 500

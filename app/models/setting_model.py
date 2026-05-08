"""
app/models/setting_model.py
Quản lý Cấu hình hệ thống (Tên shop, Banner, Tích hợp 3rd-party, Phí ship).
Cập nhật Version 3: Tích hợp Caching, Tự động khởi tạo (Auto-Init) và Shipping Rules.
"""
import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class SettingModel:
    # 1. BỘ NHỚ ĐỆM (CACHE)
    # Lưu cài đặt trên RAM để không phải gọi Database ở mỗi lần người dùng load trang.
    # Tối ưu hóa tốc độ cực kỳ hiệu quả cho hệ thống.
    _cache = None 

    # 2. BỘ CẤU HÌNH MẶC ĐỊNH (FALLBACK)
    # Dùng khi Database bị lỗi, bảng trống, hoặc khởi tạo lần đầu tiên
    DEFAULT_SETTINGS = {
        "general": {
            "shop_name": "GUA Maison",
            "hotline": "",
            "email": "",
            "timezone": "Asia/Ho_Chi_Minh",
            "warehouse_address": ""
        },
        "storefront": {
            "topbar_active": "false",
            "topbar_text": "",
            "banner_desktop_url": ""
        },
        "integrations": {
            "vnpay_tmncode": "",
            "vnpay_hashsecret": "",
            "ghn_api_token": "",
            "ghn_shop_id": ""
        },
        "shipping_rules": {
            "rules": []  # Mảng chứa danh sách các tỉnh bị tính phí ship riêng / cảnh báo
        }
    }

    @classmethod
    def get_settings(cls, force_reload=False) -> dict:
        """
        Lấy toàn bộ cấu hình hệ thống.
        Nếu force_reload=False, sẽ ưu tiên lấy từ RAM (Cache) để tối ưu tốc độ.
        """
        if not force_reload and cls._cache is not None:
            return cls._cache

        try:
            db = get_supabase()
            # Dùng .limit(1) để an toàn tuyệt đối ngay cả khi bảng trống (Tránh lỗi PGRST116)
            res = db.table("system_settings").select("*").eq("id", 1).limit(1).execute()
            
            if res.data and len(res.data) > 0:
                # Cập nhật vào bộ nhớ đệm
                cls._cache = res.data[0]
                return cls._cache
            
            # TRƯỜNG HỢP BẢNG TRỐNG: Tự động khởi tạo dòng dữ liệu mặc định!
            logger.warning("[SettingModel] Bảng system_settings đang trống. Tiến hành tự khởi tạo...")
            cls._initialize_defaults()
            return cls.DEFAULT_SETTINGS

        except Exception as e:
            logger.error(f"[SettingModel] Lỗi nghiêm trọng khi lấy Settings: {e}")
            # Dù lỗi Database, Web vẫn sống, không bị sập (dùng tạm dữ liệu cấu hình cứng)
            return cls.DEFAULT_SETTINGS

    @classmethod
    def get_section(cls, section_name: str) -> dict:
        """
        Helper hỗ trợ lấy nhanh 1 nhóm cấu hình.
        VD: SettingModel.get_section('general')
        """
        settings = cls.get_settings()
        return settings.get(section_name) or cls.DEFAULT_SETTINGS.get(section_name, {})

    @classmethod
    def update_section(cls, section_name: str, new_data: dict) -> bool:
        """
        Cập nhật từng phần cấu hình riêng lẻ.
        Sau khi lưu Database thành công sẽ tự động cập nhật lại Cache trên RAM.
        """
        # 👉 DANH SÁCH CÁC TRƯỜNG HỢP LỆ (Đã thêm shipping_rules)
        valid_sections = ["general", "storefront", "integrations", "shipping_rules"]
        
        # 1. Rào cản bảo mật (Guard Clause) để chống chèn dữ liệu bậy bạ
        if section_name not in valid_sections:
            logger.warning(f"[SettingModel] Từ chối cập nhật khu vực không hợp lệ: {section_name}")
            return False

        try:
            db = get_supabase()
            
            # 2. Lấy dữ liệu cũ từ hệ thống để chuẩn bị Merge
            current_settings = cls.get_settings()
            current_section_data = current_settings.get(section_name) or {}
            
            # 3. Kỹ thuật Merge Dictionary (Ghi đè giá trị mới lên giá trị cũ)
            # Đối với shipping_rules, do nó truyền một array ['rules': [...]], lệnh này sẽ thay thế trọn vẹn mảng cũ.
            merged_data = {**current_section_data, **new_data}
            
            # 4. Lưu trực tiếp xuống Database Supabase
            db.table("system_settings").update({
                section_name: merged_data
            }).eq("id", 1).execute()
            
            # 5. Làm mới lại Bộ nhớ đệm (Cache) ngay lập tức để giao diện nhận thay đổi
            if cls._cache:
                cls._cache[section_name] = merged_data
            else:
                cls.get_settings(force_reload=True)
                
            return True

        except Exception as e:
            logger.error(f"[SettingModel] Lỗi cập nhật khu vực {section_name}: {e}")
            return False

    @classmethod
    def _initialize_defaults(cls):
        """
        Hàm nội bộ: Tự động bơm dữ liệu chuẩn vào Database nếu lỡ bị xóa mất.
        """
        try:
            db = get_supabase()
            init_data = {
                "id": 1,
                "general": cls.DEFAULT_SETTINGS["general"],
                "storefront": cls.DEFAULT_SETTINGS["storefront"],
                "integrations": cls.DEFAULT_SETTINGS["integrations"],
                "shipping_rules": cls.DEFAULT_SETTINGS["shipping_rules"]  # Thêm mục này
            }
            # Lệnh upsert: Nếu đã có ID=1 thì update, chưa có thì insert
            db.table("system_settings").upsert(init_data).execute()
            cls._cache = init_data
            logger.info("[SettingModel] Khởi tạo dữ liệu mặc định thành công.")
        except Exception as e:
            logger.error(f"[SettingModel] Thất bại khi khởi tạo dữ liệu mặc định: {e}")

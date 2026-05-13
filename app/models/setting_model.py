"""
app/models/setting_model.py
Quản lý Cấu hình hệ thống.
Version 5: Thêm section 'admin_ui' cho giao diện Admin.
"""
import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class SettingModel:
    _cache = None

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
            "banner_desktop_url": "",
            "hero_banner_url": "",
            # Các banner mới:
            "banner2_url": "",  # ảnh cho banner full-width (section 3)
            "split_left_url": "",  # ảnh cho split bên trái
            "split_right_url": "",  # ảnh cho split bên phải
            "banner4_video_url": "",  # video cho banner 4 (best sellers)
        },
        "integrations": {
            "vnpay_tmncode": "",
            "vnpay_hashsecret": "",
            "ghn_api_token": "",
            "ghn_shop_id": ""
        },
        "shipping_rules": {
            "rules": []
        },
        "language": {
            "admin_lang": "vi",
            "date_format": "DD/MM/YYYY",
            "time_format": "24h"
        },
        # ── Thêm mới: Giao diện Admin ──
        "admin_ui": {
            "logo_url": "",
            "banner_url": ""
        }
    }

    # Tất cả sections hợp lệ (đồng bộ với controller)
    VALID_SECTIONS = [
        "general", "storefront", "integrations", "shipping_rules", "language", "admin_ui"
    ]

    @classmethod
    def get_settings(cls, force_reload=False) -> dict:
        if not force_reload and cls._cache is not None:
            return cls._cache

        try:
            db = get_supabase()
            res = db.table("system_settings").select("*").eq("id", 1).limit(1).execute()

            if res.data and len(res.data) > 0:
                cls._cache = res.data[0]
                return cls._cache

            logger.warning("[SettingModel] Bảng trống — khởi tạo defaults...")
            cls._initialize_defaults()
            return cls.DEFAULT_SETTINGS

        except Exception as e:
            logger.error(f"[SettingModel] Lỗi lấy Settings: {e}")
            return cls.DEFAULT_SETTINGS

    @classmethod
    def get_section(cls, section_name: str) -> dict:
        settings = cls.get_settings()
        return settings.get(section_name) or cls.DEFAULT_SETTINGS.get(section_name, {})

    @classmethod
    def update_section(cls, section_name: str, new_data: dict) -> bool:
        if section_name not in cls.VALID_SECTIONS:
            logger.warning(f"[SettingModel] Từ chối section không hợp lệ: {section_name}")
            return False

        try:
            db = get_supabase()
            current_settings = cls.get_settings()
            current_section_data = current_settings.get(section_name) or {}
            merged_data = {**current_section_data, **new_data}

            db.table("system_settings").update({
                section_name: merged_data
            }).eq("id", 1).execute()

            if cls._cache:
                cls._cache[section_name] = merged_data
            else:
                cls.get_settings(force_reload=True)

            return True

        except Exception as e:
            logger.error(f"[SettingModel] Lỗi update {section_name}: {e}")
            return False

    @classmethod
    def _initialize_defaults(cls):
        try:
            db = get_supabase()
            init_data = {"id": 1, **cls.DEFAULT_SETTINGS}
            db.table("system_settings").upsert(init_data).execute()
            cls._cache = init_data
            logger.info("[SettingModel] Khởi tạo defaults thành công.")
        except Exception as e:
            logger.error(f"[SettingModel] Thất bại khởi tạo defaults: {e}")

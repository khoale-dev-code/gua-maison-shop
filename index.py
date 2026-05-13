import os

# 1. NẠP BIẾN MÔI TRƯỜNG (Dành riêng cho Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app import create_app
# --- THÊM DÒNG NÀY ĐỂ GỌI MODEL SETTINGS ---
from app.models.setting_model import SettingModel 

# 2. KHỞI TẠO ỨNG DỤNG FLASK
app = create_app()


# ═══════════════════════════════════════════════════════════════
#  BƯỚC 5: GLOBAL CONTEXT PROCESSOR (BẮT BUỘC)
#  Giúp bạn gọi {{ global_settings.hotline }} ở bất cứ đâu (Header, Footer...)
# ═══════════════════════════════════════════════════════════════
@app.context_processor
def inject_global_settings():
    """Tự động lấy cấu hình cửa hàng từ DB và đưa vào mọi template HTML"""
    try:
        store_settings = SettingModel.get_settings("general")
        return dict(global_settings=store_settings)
    except Exception:
        # Trả về giá trị mặc định nếu DB lỗi để web không bị crash
        return dict(global_settings={
            "store_name": "GUA Maison",
            "hotline": "N/A",
            "email": "N/A"
        })


# 3. MÁY CHỦ PHÁT TRIỂN (Local Development)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_debug = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    
    print("=" * 55)
    print("🚀 GUA MAISON 2026 - SERVER IS STARTING...")
    print(f"🌍 Truy cập tại     : http://127.0.0.1:{port}")
    print(f"🛠️  Chế độ Debug    : {'BẬT (Development)' if is_debug else 'TẮT (Production)'}")
    print("=" * 55)
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=is_debug
    )

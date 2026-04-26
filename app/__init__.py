"""
app/__init__.py  –  Application Factory (GUA SPORT 2026 Edition)
"""
import logging
from flask import Flask, session, redirect, render_template_string
# from flask_session import Session # 🛑 ĐÃ ẨN: Không dùng Flask-Session trên Vercel để tránh lỗi Read-only OS
from flask_wtf.csrf import CSRFProtect, CSRFError
from config.settings import get_config

# Cấu hình Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo các Extensions ngoài factory
# sess = Session() # 🛑 ĐÃ ẨN: Ép Flask dùng cơ chế Cookie Session mặc định
csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # 1. Load Cấu hình
    app.config.from_object(get_config())

    # 2. Khởi tạo Extensions
    # sess.init_app(app) # 🛑 ĐÃ ẨN: Bỏ qua bước tạo thư mục flask_session trên máy chủ
    csrf.init_app(app)  # Kích hoạt bảo vệ CSRF toàn cục

    # 3. Đăng ký Blueprints
    from app.controllers.auth_controller    import auth_bp
    from app.controllers.product_controller import products_bp
    from app.controllers.cart_controller    import cart_bp
    from app.controllers.admin_controller   import admin_bp
    from app.controllers.profile_controller import profile_bp
    from app.controllers.debug_controller   import debug_bp
    from app.controllers.chat_controller    import chat_bp  # Đã thêm Chatbot Blueprint

    blueprints = [
        (auth_bp, None),
        (products_bp, None),
        (cart_bp, None),
        (admin_bp, None),
        (profile_bp, None),
        (debug_bp, None),
        (chat_bp, None)  # Đã đăng ký Chatbot vào mảng
    ]

    for bp, prefix in blueprints:
        app.register_blueprint(bp, url_prefix=prefix)

    # 4. Context Processor: Truyền biến toàn cục vào Jinja2
    @app.context_processor
    def inject_globals():
        cart_count = 0
        user_id = session.get("user_id")
        
        # Xử lý số lượng giỏ hàng
        if user_id:
            try:
                from app.models.cart_model import CartModel
                cart_count = CartModel.get_count(user_id)
            except Exception:
                logger.error("Failed to fetch cart count in context_processor")
                cart_count = 0
                
        # Xử lý Danh mục động cho toàn bộ trang (Navbar, Sidebar)
        try:
            from app.models.category_model import CategoryModel
            categories = CategoryModel.get_all()
        except Exception:
            logger.error("Failed to fetch categories in context_processor")
            categories = []
            
        return {
            "current_user": {
                "id": session.get("user_id"),
                "email": session.get("email"),
                "full_name": session.get("full_name"),
                "role": session.get("role"),
            },
            "cart_count": cart_count,
            "global_categories": categories,  # Truyền danh mục ra toàn cục
        }

    # 5. Xử lý lỗi hệ thống (Error Handlers)
    
    @app.errorhandler(404)
    def not_found(e):
        """Giao diện 404 phong cách Sport-Luxe mạnh mẽ."""
        return render_template_string(ERROR_TEMPLATE,
            code=404,
            title="Không tìm thấy trang",
            desc="Đường dẫn này không tồn tại hoặc đã bị xóa khỏi hệ thống."), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Xử lý lỗi Token bảo mật hết hạn hoặc thiếu."""
        return render_template_string(ERROR_TEMPLATE,
            code=403,
            title="Từ chối truy cập",
            desc="Phiên làm việc đã hết hạn hoặc thiếu mã bảo mật. Vui lòng tải lại trang."), 403

    @app.errorhandler(500)
    def server_error(e):
        """Giao diện lỗi 500 chuyên nghiệp."""
        logger.exception("Internal Server Error")
        return render_template_string(ERROR_TEMPLATE,
            code=500,
            title="Lỗi máy chủ",
            desc="Hệ thống đang gặp sự cố kỹ thuật. Vui lòng quay lại sau ít phút."), 500

    return app


# ═══════════════════════════════════════════════════════════════
# TEMPLATE LỖI CHUẨN SPORT-LUXE (STREETWEAR VIBE)
# ═══════════════════════════════════════════════════════════════
ERROR_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ code }} - GUA SPORT</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700;900&display=swap" rel="stylesheet">
    <style>body { font-family: 'DM Sans', sans-serif; }</style>
</head>
<body class="bg-white flex items-center justify-center min-h-screen px-4 py-12">
    <div class="max-w-2xl w-full bg-stone-50 border-[4px] border-black p-10 md:p-20 text-center shadow-[16px_16px_0px_0px_rgba(0,0,0,1)]">
        
        <h1 class="text-[80px] md:text-[140px] font-black text-black leading-none tracking-tighter mb-2">
            {{ code }}
        </h1>
        
        <div class="h-2 w-20 bg-black mx-auto mb-8"></div>
        
        <h2 class="text-[28px] md:text-[36px] font-black text-black uppercase tracking-tight mb-4">
            {{ title }}
        </h2>
        
        <p class="text-stone-500 text-[14px] font-bold uppercase tracking-widest mb-12 max-w-md mx-auto leading-relaxed">
            {{ desc }}
        </p>
        
        <div class="flex flex-col items-center gap-6">
            <a href="/" class="block w-full sm:w-auto bg-black text-white px-12 py-5 font-black uppercase tracking-[0.1em] text-[15px] hover:bg-stone-800 active:scale-95 transition-all">
                Về trang chủ
            </a>
            
            {% if code == 500 %}
            <a href="/debug/test-db" class="inline-block text-[12px] text-stone-400 font-black uppercase tracking-widest hover:text-black border-b-2 border-transparent hover:border-black transition-all">
                KIỂM TRA DATABASE
            </a>
            {% endif %}
        </div>
        
    </div>
</body>
</html>
"""

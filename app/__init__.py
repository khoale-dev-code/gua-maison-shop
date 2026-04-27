"""
app/__init__.py  –  Application Factory (GUA MAISON 2026 Edition)
"""
import logging
from flask import Flask, session, redirect, render_template_string
from flask_wtf.csrf import CSRFProtect, CSRFError
from config.settings import get_config

# Cấu hình Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo CSRF Protect
csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # 1. Load Cấu hình
    app.config.from_object(get_config())

    # 2. Khởi tạo Extensions
    csrf.init_app(app)  # Kích hoạt bảo vệ CSRF toàn cục

    # 3. Đăng ký Blueprints
    from app.controllers.auth_controller    import auth_bp
    from app.controllers.product_controller import products_bp
    from app.controllers.cart_controller    import cart_bp
    from app.controllers.admin_controller   import admin_bp
    from app.controllers.profile_controller import profile_bp
    from app.controllers.debug_controller   import debug_bp
    from app.controllers.chat_controller    import chat_bp
    from app.controllers.ai_controller      import ai_bp  # <-- Đăng ký thêm AI Styling Lab

    blueprints = [
        (auth_bp, None),
        (products_bp, None),
        (cart_bp, None),
        (admin_bp, None),
        (profile_bp, None),
        (debug_bp, None),
        (chat_bp, None),
        (ai_bp, None)  # <-- Đăng ký ai_bp vào hệ thống
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
        """Giao diện 404 phong cách Minimalist Sport-Luxe."""
        return render_template_string(ERROR_TEMPLATE,
            code=404,
            title="Không tìm thấy trang",
            desc="Đường dẫn này không tồn tại hoặc đã bị gỡ khỏi hệ thống GUA Maison."), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Xử lý lỗi Token bảo mật hết hạn hoặc thiếu."""
        return render_template_string(ERROR_TEMPLATE,
            code=403,
            title="Từ chối truy cập",
            desc="Phiên làm việc đã hết hạn do bảo mật. Vui lòng tải lại trang và thử lại."), 403

    @app.errorhandler(500)
    def server_error(e):
        """Giao diện lỗi 500 chuyên nghiệp."""
        logger.exception("Internal Server Error")
        return render_template_string(ERROR_TEMPLATE,
            code=500,
            title="Lỗi máy chủ",
            desc="Hệ thống đang gặp sự cố kỹ thuật. Đội ngũ kỹ sư của chúng tôi đang xử lý."), 500

    return app


# ═══════════════════════════════════════════════════════════════
# TEMPLATE LỖI CHUẨN MINIMALIST SPORT-LUXE 2026
# ═══════════════════════════════════════════════════════════════
ERROR_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ code }} - GUA Maison</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'DM Sans', sans-serif; }
        .reveal { animation: revealUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards; opacity: 0; }
        @keyframes revealUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-stone-50 flex items-center justify-center min-h-screen px-4 py-12 relative overflow-hidden">
    
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-stone-200 rounded-full blur-[100px] pointer-events-none z-0"></div>

    <div class="max-w-2xl w-full bg-white/80 backdrop-blur-xl border border-stone-200/60 rounded-3xl p-10 md:p-20 text-center shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] relative z-10 reveal">
        
        <div class="flex justify-center mb-6">
            <div class="w-16 h-16 bg-stone-100 rounded-full flex items-center justify-center text-stone-400">
                {% if code == 404 %}
                <svg class="w-8 h-8" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
                {% elif code == 403 %}
                <svg class="w-8 h-8" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/></svg>
                {% else %}
                <svg class="w-8 h-8" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                {% endif %}
            </div>
        </div>

        <h1 class="text-7xl md:text-9xl font-black text-stone-900 leading-none tracking-tighter mb-4 drop-shadow-sm">
            {{ code }}
        </h1>
        
        <h2 class="text-xl md:text-3xl font-bold text-stone-900 tracking-tight mb-4">
            {{ title }}
        </h2>
        
        <p class="text-stone-500 text-sm font-medium mb-10 max-w-md mx-auto leading-relaxed">
            {{ desc }}
        </p>
        
        <div class="flex flex-col items-center gap-4">
            <a href="/" class="block w-full sm:w-auto bg-stone-900 text-white px-10 py-4 rounded-xl text-sm font-bold shadow-lg hover:bg-stone-700 hover:-translate-y-1 active:scale-95 transition-all duration-300">
                Trở về Trang chủ
            </a>
            
            {% if code == 500 %}
            <a href="/debug/test-db" class="inline-block text-xs text-stone-400 font-bold hover:text-stone-900 underline underline-offset-4 transition-colors mt-4">
                Chạy trình kiểm tra CSDL
            </a>
            {% endif %}
        </div>
        
    </div>
</body>
</html>
"""

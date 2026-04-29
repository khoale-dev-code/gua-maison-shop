import logging
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from pydantic import ValidationError

from app.schemas.favorite_schema import FavoriteToggleRequest
from app.services.favorite_service import FavoriteService

logger = logging.getLogger(__name__)
favorite_bp = Blueprint('favorite_bp', __name__)


@favorite_bp.route('/api/favorites/toggle', methods=['POST'])
def toggle_favorite() -> tuple:
    """API Toggle Favorite với Typing, Validation và Layered Architecture"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Vui lòng đăng nhập"}), 401

    try:
        # 1. Pydantic Validation (Tự động ném ValidationError nếu product_id bị thiếu hoặc sai kiểu)
        req_data = FavoriteToggleRequest(**request.get_json() or {})
        
        # 2. Chuyển xuống Service Layer xử lý
        result = FavoriteService.toggle_favorite(user_id, req_data.product_id)
        
        # 3. Trả về kết quả
        return jsonify(result), 200

    except ValidationError as ve:
        logger.warning(f"[VALIDATION_ERROR] {ve.errors()}")
        return jsonify({"status": "error", "message": "Dữ liệu đầu vào không hợp lệ"}), 400
        
    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
        
    except Exception as e:
        logger.error(f"[CONTROLLER_ERROR] Unhandled exception: {e}")
        return jsonify({"status": "error", "message": "Lỗi máy chủ nội bộ"}), 500


@favorite_bp.route('/profile/favorites', methods=['GET'])
def wishlist_page() -> str:
    user_id = session.get('user_id')
    if not user_id:
        # Dùng url_for thay vì hardcode chuỗi
        return redirect(url_for('auth_bp.login'))
        
    try:
        # Nhận tham số page từ URL (ví dụ: ?page=2), mặc định là 1
        page = int(request.args.get('page', 1))
        
        # Gọi Service có phân trang
        favorites = FavoriteService.get_user_wishlist(user_id, page=page)
        
        return render_template('profile/favorites.html', favorites=favorites)
        
    except ValueError:
        return render_template('errors/400.html', message="Tham số trang không hợp lệ"), 400
    except Exception as e:
        logger.error(f"[PAGE_ERROR] Failed to load wishlist page: {e}")
        return render_template('errors/500.html'), 500

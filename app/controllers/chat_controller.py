"""
app/controllers/chat_controller.py
Xử lý API cho Smart AI Ecommerce Assistant.
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.chat_service import AdvancedChatService

logger = logging.getLogger(__name__)

# Khởi tạo Blueprint (đảm bảo tên biến là chat_bp để app/__init__.py import đúng)
chat_bp = Blueprint('chat_bp', __name__)


@chat_bp.route('/api/bot', methods=['POST'])
def bot_reply():
    try:
        # Lấy dữ liệu JSON từ Frontend (file chat.html gửi lên)
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "anonymous_session")
        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "reply": "Vui lòng nhập tin nhắn để GUA Assistant hỗ trợ bạn nhé.",
                "intent": "error"
            }), 400

        # Gọi class AI mới (truyền cả session_id để AI nhớ context chat)
        response_data = AdvancedChatService.process_message(session_id, message)
        
        # Trả về nguyên cục JSON chuẩn Pydantic cho Frontend tự render giao diện
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"[Chat API Error] {e}")
        return jsonify({
            "reply": "Hệ thống AI đang bảo trì. Bạn có thể nhắn tin cho GUA qua Fanpage để được hỗ trợ nhanh nhất nhé!",
            "intent": "error"
        }), 500

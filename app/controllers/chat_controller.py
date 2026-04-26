from flask import Blueprint, request, jsonify
from app.services.chat_service import ChatService

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/api/bot", methods=["POST"])
def chat_bot():
    """Endpoint xử lý tin nhắn của SYS_BOT"""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": "Lỗi truy xuất dữ liệu."}), 400
        
    user_msg = data.get("message", "")
    bot_reply = ChatService.get_response(user_msg)
    
    return jsonify({"reply": bot_reply})
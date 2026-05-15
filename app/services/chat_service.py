"""
app/services/chat_service.py
Smart AI Assistant - Tích hợp Gemini 3 & Phối đồ thông minh (Outfit Suggestion)
"""
import os
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.schemas.chat_schema import ChatResponse, ExtractedIntent, ProductSuggestion
from app.utils.supabase_client import get_supabase

# Load biến môi trường
load_dotenv()
logger = logging.getLogger(__name__)

# ─── 1. KHỞI TẠO LLM CLIENT (GEMINI 3 FLASH) ───
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
else:
    logger.warning("CẢNH BÁO: Chưa cấu hình GEMINI_API_KEY trong file .env")
    client = None

# Bộ nhớ hội thoại (Memory)
CONVERSATION_MEMORY = {}


class AdvancedChatService:
    # Bảng size chuẩn của shop
    SIZE_CHART = {
        "S": {"max_h": 168, "max_w": 55},
        "M": {"max_h": 174, "max_w": 65},
        "L": {"max_h": 180, "max_w": 75},
        "XL": {"max_h": 190, "max_w": 90}
    }

    @classmethod
    def get_history(cls, session_id: str) -> list:
        if session_id not in CONVERSATION_MEMORY:
            CONVERSATION_MEMORY[session_id] = []
        return CONVERSATION_MEMORY[session_id]

    @classmethod
    def save_to_memory(cls, session_id: str, role: str, content: str):
        history = cls.get_history(session_id)
        history.append({"role": role, "content": content})
        if len(history) > 10: 
            history.pop(0)

    @classmethod
    def process_message(cls, session_id: str, message: str) -> dict:
        cls.save_to_memory(session_id, "user", message)
        history = cls.get_history(session_id)

        try:
            if not client: raise Exception("Chưa khởi tạo LLM Client.")

            # ─── 2. CẤU HÌNH PROMPT STYLIST THÔNG MINH ───
            system_prompt = """Bạn là GUA Assistant, trợ lý ảo cao cấp và Stylist thời trang của GUA Maison.
            Giọng điệu: Sang trọng, tinh tế nhưng gần gũi.
            
            QUY TẮC PHÂN LOẠI Ý ĐỊNH (INTENT):
            1. outfit_suggestion: Khi khách muốn phối đồ, gợi ý set đồ, hỏi "mặc gì đẹp", hoặc yêu cầu "phối quần với áo".
            2. search_product: Khi khách tìm món đồ cụ thể hoặc muốn xem mẫu mã nói chung.
            3. size_advice: Khi khách hỏi về kích cỡ, số đo chiều cao cân nặng.
            4. order_tracking: Tra cứu đơn hàng qua SĐT hoặc mã đơn.
            5. policy_info: Hỏi địa chỉ, đổi trả, bảo hành.
            6. promotion_info: Hỏi về khuyến mãi, voucher.
            
            Lưu ý: Với `outfit_suggestion`, hãy viết câu trả lời khơi gợi cảm hứng thời trang."""

            chat_context = ""
            for h in history[:-1]:
                speaker = "Khách" if h["role"] == "user" else "GUA Assistant"
                chat_context += f"{speaker}: {h['content']}\n"
            
            prompt = f"Lịch sử trò chuyện:\n{chat_context}\n\nTin nhắn mới của Khách: {message}\n\nHãy phân tích và phản hồi."

            # Gọi Gemini 3 bóc tách dữ liệu
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=ExtractedIntent,
                    temperature=0.2,
                )
            )

            ai_data: ExtractedIntent = response.parsed
            response_data = ChatResponse(reply=ai_data.reply, intent=ai_data.intent)

            # ─── 3. ĐIỀU HƯỚNG XỬ LÝ ───
            
            # Ý định: PHỐI ĐỒ (1 Áo + 1 Quần)
            if ai_data.intent == "outfit_suggestion":
                response_data = cls._fetch_outfit_from_db(response_data)

            # Ý định: TƯ VẤN SIZE
            elif ai_data.intent == "size_advice":
                if ai_data.height and ai_data.weight:
                    rec_size = "S"
                    for s, limits in cls.SIZE_CHART.items():
                        if ai_data.height <= limits["max_h"] and ai_data.weight <= limits["max_w"]:
                            rec_size = s; break
                        rec_size = "XL"
                    response_data.reply = f"Với form của GUA, bạn mặc size **{rec_size}** là đẹp nhất nhé. Bạn muốn GUA gợi ý set đồ nào phù hợp không?"
                    response_data.action_data = {"height": ai_data.height, "weight": ai_data.weight, "recommended_size": rec_size}
                else:
                    response_data.reply = "Để tư vấn size chuẩn nhất, bạn cho GUA xin **chiều cao** và **cân nặng** nhé! ✨"

            # Ý định: TÌM SẢN PHẨM
            elif ai_data.intent == "search_product":
                response_data = cls._fetch_products_from_db(ai_data.keywords, ai_data.is_general_request, response_data)

            # Ý định: TRA CỨU ĐƠN HÀNG
            elif ai_data.intent == "order_tracking":
                if ai_data.phone or ai_data.order_code:
                    response_data = cls._handle_order_tracking(ai_data.phone, ai_data.order_code, response_data)
                else:
                    response_data.reply = "Cho GUA xin **SĐT đặt hàng** hoặc **Mã đơn** để kiểm tra nhé! 📦"

            # Các ý định thông tin khác
            elif ai_data.intent == "policy_info":
                response_data.reply = "📍 **Địa chỉ:** 123 Nguyễn Trãi, Q1, HCM.<br>🔄 **Đổi trả:** Miễn phí trong 7 ngày.<br>🚚 **Vận chuyển:** Freeship đơn từ 500k."
            elif ai_data.intent == "promotion_info":
                response_data.reply = "Dùng mã **WELCOME10** để được giảm ngay 10% cho đơn hàng đầu tiên bạn nhé! 🎟️"

            cls.save_to_memory(session_id, "assistant", response_data.reply)
            return response_data.model_dump()

        except Exception as e:
            logger.error(f"[Chat API] Error: {e}")
            return ChatResponse(reply="Hệ thống đang tải lại dữ liệu, bạn vui lòng đợi xíu nhé! 🖤", intent="general_chat").model_dump()

    # ─── 4. CÁC HÀM XỬ LÝ DATABASE (SUPABASE) ───

    @classmethod
    def _fetch_outfit_from_db(cls, response_data: ChatResponse) -> ChatResponse:
        """Hàm bốc 1 Top và 1 Bottom để tạo Set đồ"""
        db = get_supabase()
        try:
            # Lấy 1 sản phẩm thuộc loại 'Áo'
            top_res = db.table("products").select("id, name, price, thumbnail_url, slug").eq("is_active", True).is_("deleted_at", "null").or_("name.ilike.%áo%,name.ilike.%tee%,name.ilike.%shirt%").order("created_at", desc=True).limit(1).execute()
            
            # Lấy 1 sản phẩm thuộc loại 'Quần'
            bottom_res = db.table("products").select("id, name, price, thumbnail_url, slug").eq("is_active", True).is_("deleted_at", "null").or_("name.ilike.%quần%,name.ilike.%pants%,name.ilike.%short%").order("created_at", desc=True).limit(1).execute()

            outfit_items = (top_res.data or []) + (bottom_res.data or [])

            if len(outfit_items) >= 2:
                response_data.reply = "GUA gợi ý cho bạn một set đồ hoàn hảo để dạo phố hôm nay: một chiếc áo phối cùng quần form rộng chuẩn GUA Style. Xem thử nhé! ✨"
                response_data.products = [
                    ProductSuggestion(
                        id=str(p["id"]), name=p["name"],
                        price="{:,.0f}".format(float(p["price"])),
                        thumbnail_url=p["thumbnail_url"] or "https://placehold.co/100/e2e8f0/1c1917?text=GUA",
                        slug=p["slug"]
                    ) for p in outfit_items
                ]
            else:
                return cls._fetch_products_from_db([], True, response_data)  # Fallback về mẫu mới nhất
        except Exception as e:
            logger.error(f"Lỗi phối đồ: {e}")
        return response_data

    @classmethod
    def _fetch_products_from_db(cls, keywords: list, is_general: bool, response_data: ChatResponse) -> ChatResponse:
        db = get_supabase()
        try:
            query = db.table("products").select("id, name, price, thumbnail_url, slug").eq("is_active", True).is_("deleted_at", "null")
            
            if is_general:
                query = query.order("created_at", desc=True)
                response_data.reply = "GUA gửi bạn các mẫu thiết kế mới nhất vừa 'on web' nhé! 🔥"
            elif keywords:
                or_conditions = ",".join([f"name.ilike.%{kw}%" for kw in keywords])
                query = query.or_(or_conditions)
            
            res = query.limit(3).execute()
            products_data = res.data or []

            # Fallback nếu không tìm thấy
            if not products_data and not is_general:
                res = db.table("products").select("id, name, price, thumbnail_url, slug").eq("is_active", True).is_("deleted_at", "null").order("created_at", desc=True).limit(3).execute()
                products_data = res.data or []
                response_data.reply = "Mẫu bạn tìm hiện đã hết, nhưng GUA gợi ý bạn những mẫu 'best-seller' này mặc cũng cực cháy luôn! 🖤"

            if products_data:
                response_data.products = [
                    ProductSuggestion(
                        id=str(p["id"]), name=p["name"],
                        price="{:,.0f}".format(float(p["price"])),
                        thumbnail_url=p.get("thumbnail_url") or "https://placehold.co/100/e2e8f0/1c1917?text=GUA",
                        slug=p["slug"]
                    ) for p in products_data
                ]
        except Exception as e:
            logger.error(f"Lỗi DB: {e}")
        return response_data

    @classmethod
    def _handle_order_tracking(cls, phone: str, order_code: str, response_data: ChatResponse) -> ChatResponse:
        db = get_supabase()
        try:
            query = db.table("orders").select("code, status, total_amount, created_at")
            if order_code: query = query.eq("code", order_code.upper())
            elif phone: query = query.eq("customer_phone", phone)
            
            res = query.order("created_at", desc=True).limit(1).execute()
            if res.data:
                order = res.data[0]
                status_map = {"pending": "Chờ xác nhận ⏳", "confirmed": "Đã xác nhận 📦", "shipped": "Đang giao 🚚", "delivered": "Đã giao ✅", "cancelled": "Đã hủy ❌"}
                status_text = status_map.get(order["status"], order["status"])
                total_fmt = "{:,.0f}".format(float(order["total_amount"]))
                
                response_data.reply = f"<div class='bg-slate-50 border border-slate-200 p-3 rounded-xl mb-2'><div class='flex justify-between mb-2 pb-2 border-b border-slate-200'><span class='text-[10px] font-bold text-slate-400 uppercase'>Mã đơn</span><span class='text-xs font-mono font-bold text-slate-900'>{order['code']}</span></div><div class='flex justify-between text-[13px]'><span class='text-slate-500'>Trạng thái:</span><span class='font-bold text-emerald-600'>{status_text}</span></div><div class='flex justify-between text-[13px] mt-1'><span class='text-slate-500'>Tổng tiền:</span><span class='font-bold text-slate-900'>{total_fmt} ₫</span></div></div> GUA đã kiểm tra xong, đơn hàng của bạn đang ở trạng thái trên nhé!"
            else:
                response_data.reply = "GUA không tìm thấy đơn hàng nào khớp với thông tin này. Bạn kiểm tra lại SĐT hoặc Mã đơn nhé! 🧐"
        except Exception: pass
        return response_data

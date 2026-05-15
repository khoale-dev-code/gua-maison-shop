"""
app/schemas/chat_schema.py
Định nghĩa cấu trúc dữ liệu cho Chatbot bằng Pydantic.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# --- 1. Model dành cho Request từ Frontend ---
class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID phiên chat để AI quản lý bộ nhớ (Conversation Memory)")
    message: str = Field(..., description="Tin nhắn của người dùng gửi lên")


# --- 2. Model đại diện cho một sản phẩm gợi ý trong khung chat ---
class ProductSuggestion(BaseModel):
    id: str
    name: str
    price: str
    thumbnail_url: str
    slug: str


# --- 3. Model Response cuối cùng mà Backend trả về cho giao diện (Frontend) ---
class ChatResponse(BaseModel):
    reply: str = Field(..., description="Câu trả lời tự nhiên của AI đã được xử lý")
    intent: str = Field(..., description="Ý định cuối cùng được xác định (search_product, size_advice, outfit_suggestion, v.v.)")
    products: Optional[List[ProductSuggestion]] = Field(default=[], description="Danh sách các sản phẩm lấy từ Database")
    action_data: Optional[Dict[str, Any]] = Field(default={}, description="Dữ liệu bổ sung như thông số size hoặc thông tin đơn hàng")


# --- 4. Model dành riêng cho Gemini bóc tách dữ liệu (NLU) ---
# Schema này giúp Gemini hiểu và phân loại tin nhắn một cách thông minh
class ExtractedIntent(BaseModel):
    reply: str = Field(..., description="Câu trả lời thân thiện, lịch sự, đúng phong cách sang trọng của GUA Maison.")
    
    # [QUAN TRỌNG] Đã bổ sung 'outfit_suggestion' vào danh sách phân loại ý định
    intent: str = Field(..., description="Phân loại ý định: general_chat, search_product, size_advice, order_tracking, policy_info, promotion_info, outfit_suggestion")
    
    keywords: Optional[List[str]] = Field(
        default=[],
        description="Từ khóa ĐÃ DỊCH SANG LOẠI TRANG PHỤC. Ví dụ: khách nói 'đi du lịch' -> keywords: ['áo thun', 'quần short', 'oversize']. Đừng lấy nguyên văn từ khóa nếu nó mang tính hoàn cảnh."
    )
    
    is_general_request: Optional[bool] = Field(
        default=False,
        description="Đặt là True nếu khách chỉ muốn xem mẫu chung chung như 'cho xem đồ', 'shop có gì mới', 'gợi ý mẫu hot'."
    )
    
    height: Optional[int] = Field(default=None, description="Chiều cao khách hàng (cm)")
    weight: Optional[int] = Field(default=None, description="Cân nặng khách hàng (kg)")
    phone: Optional[str] = Field(default=None, description="Số điện thoại khách hàng trích xuất được")
    order_code: Optional[str] = Field(default=None, description="Mã đơn hàng (Ví dụ: ORD123456 hoặc POS654321)")

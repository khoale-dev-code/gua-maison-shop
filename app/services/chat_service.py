import re
import random


class ChatService:

    @staticmethod
    def get_response(message: str) -> str:
        msg = message.lower()

        # 1. SALES AI: HỎI GIÁ / TỒN KHO / CHỐT ĐƠN (Cực mạnh)
        if any(word in msg for word in ["giá", "bao nhiêu", "tiền", "còn size", "còn hàng", "mua"]):
            # [TODO: Gọi Supabase Query để lấy sản phẩm thực tế theo keyword]
            # Ở đây giả lập trả về 1 Card sản phẩm có nút Mua Ngay
            return """
            <div class='mb-2'>Mẫu này bên mình vẫn còn hàng và đang có mức giá cực kỳ tốt. Chốt đơn ngay kẻo lỡ size nhé! 🔥</div>
            
            <div class='product-card mt-3 bg-stone-50 border border-stone-200 rounded-xl p-2 flex items-center gap-3'>
                <div class='w-14 h-16 bg-stone-200 rounded-lg overflow-hidden shrink-0'>
                    <img src='https://placehold.co/100x150/e2e8f0/1c1917?text=GUA+TEE' class='w-full h-full object-cover'/>
                </div>
                <div class='flex-1'>
                    <p class='text-xs font-bold text-stone-900'>GUA Heritage Signature Tee</p>
                    <p class='text-xs font-semibold text-stone-500 mt-0.5'>850,000 ₫</p>
                </div>
            </div>
            
            <a href='/shop' class='mt-3 block w-full bg-stone-900 text-white text-center text-xs font-bold py-2.5 rounded-lg shadow-md hover:bg-stone-700 transition-colors'>
                THÊM VÀO GIỎ HÀNG
            </a>
            """

        # 2. SEARCH AI & MIX MATCH: TÌM KIẾM / PHỐI ĐỒ
        search_keywords = ["tìm", "áo", "quần", "streetwear", "form rộng", "mặc đi chơi", "phối đồ", "mix"]
        if any(word in msg for word in search_keywords):
            # [TODO: Gọi Supabase Query LIKE %...% dựa trên msg]
            return """
            <div class='mb-3'>Mình đã phân tích style của bạn. Dưới đây là các item streetwear chuẩn form rộng rất hợp để đi chơi:</div>
            
            <div class='flex flex-col gap-2'>
                <a href='/shop' class='product-card flex items-center gap-3 p-2 bg-white border border-stone-200 hover:border-stone-400 rounded-xl transition-all'>
                    <div class='w-12 h-14 bg-stone-100 rounded-md overflow-hidden'>
                        <img src='https://placehold.co/100x120/e2e8f0/1c1917?text=AO+DEN' class='w-full h-full object-cover'/>
                    </div>
                    <div>
                        <p class='text-xs font-bold text-stone-900'>Áo thun Oversize Đen</p>
                        <p class='text-[10px] font-medium text-stone-500'>650,000 ₫</p>
                    </div>
                </a>
                
                <a href='/shop' class='product-card flex items-center gap-3 p-2 bg-white border border-stone-200 hover:border-stone-400 rounded-xl transition-all'>
                    <div class='w-12 h-14 bg-stone-100 rounded-md overflow-hidden'>
                        <img src='https://placehold.co/100x120/e2e8f0/1c1917?text=CARGO' class='w-full h-full object-cover'/>
                    </div>
                    <div>
                        <p class='text-xs font-bold text-stone-900'>Quần Cargo Túi Hộp</p>
                        <p class='text-[10px] font-medium text-stone-500'>950,000 ₫</p>
                    </div>
                </a>
            </div>
            """

        # 3. TƯ VẤN SIZE (Phân tích chiều cao cân nặng)
        height_match = re.search(r'(\d+m\d+|\d{3}\s*cm)', msg)
        weight_match = re.search(r'(\d+)\s*(kg|kí|ki)', msg)

        if height_match or weight_match or "size" in msg:
            if height_match and weight_match:
                h_str = height_match.group(1).replace('m', '').replace('cm', '')
                if len(h_str) == 2: h_str += '0'
                h = int(h_str) if len(h_str) == 3 else int(h_str) * 100
                w = int(weight_match.group(1))

                size = "S"
                if h <= 172 and w <= 70: size = "M"
                elif h <= 178 and w <= 80: size = "L"
                elif h > 178 or w > 80: size = "XL"

                return f"""
                <div class='bg-stone-50 border border-stone-200 p-3 rounded-xl mb-2'>
                    <p class='text-xs text-stone-600'>📊 Thông số: Cao <b>{h}cm</b> - Nặng <b>{w}kg</b></p>
                </div>
                Theo chuẩn đo lường của GUA, bạn mặc <b>Size {size}</b> là lên form đẹp nhất nhé. Cần mình gợi ý mẫu nào đang hot không?
                """
            else:
                return "Để mình tính toán chuẩn xác nhất, bạn nhập giúp mình cả <b>chiều cao</b> và <b>cân nặng</b> nhé (Ví dụ: 1m70 60kg)."

        # 4. CHÀO HỎI
        if any(word in msg for word in ["hello", "chào", "hi ", "ơi"]):
            return "GUA Assistant xin chào! 👋 Bạn cần tìm đồ đi chơi, tư vấn size hay check đơn hàng nào?"

        # 5. FALLBACK
        return "Mình chưa hiểu rõ ý bạn lắm. Bạn có thể nhập <b>chiều cao cân nặng</b> để tư vấn size, hoặc gõ tên sản phẩm bạn đang tìm nhé!"

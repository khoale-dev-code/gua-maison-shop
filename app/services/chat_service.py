import re
import random

class ChatService:
    @staticmethod
    def get_response(message: str) -> str:
        msg = message.lower()

        # 1. NHẬN DIỆN Ý ĐỊNH TƯ VẤN SIZE (Rule-based logic)
        # Bắt các format: 1m70, 1m7, 170cm, 65kg, 65 kí...
        height_match = re.search(r'(\d+m\d+|\d{3}\s*cm)', msg)
        weight_match = re.search(r'(\d+)\s*(kg|kí|ki)', msg)

        if height_match or weight_match or "size" in msg:
            if height_match and weight_match:
                # Xử lý chuỗi để lấy ra con số tính toán
                h_str = height_match.group(1).replace('m', '').replace('cm', '')
                if len(h_str) == 2: h_str += '0' # Xử lý "1m7" thành "170"
                
                h = int(h_str) if len(h_str) == 3 else int(h_str)*100 # Nếu là 170
                w = int(weight_match.group(1))

                # Logic tính size chuẩn GUA
                if h < 165 and w < 60: return f"Hệ thống phân tích: Chiều cao {h}cm, Nặng {w}kg. Size S là lựa chọn tối ưu nhất cho bạn."
                elif h <= 172 and w <= 70: return f"Hệ thống phân tích: Chiều cao {h}cm, Nặng {w}kg. Bạn nên chọn Size M để vừa vặn."
                elif h <= 178 and w <= 80: return f"Hệ thống phân tích: Chiều cao {h}cm, Nặng {w}kg. Size L sẽ mang lại form dáng thoải mái nhất."
                else: return f"Hệ thống phân tích: Chiều cao {h}cm, Nặng {w}kg. Bạn vui lòng chọn Size XL nhé."
            else:
                return "Để tính toán chính xác nhất, bạn hãy cung cấp cả chiều cao và cân nặng (Ví dụ: 'Tôi cao 1m75 nặng 70kg')."

        # 2. NHẬN DIỆN Ý ĐỊNH PHỐI ĐỒ (Cross-selling)
        if any(word in msg for word in ["phối", "mix", "mặc với", "kết hợp"]):
            return ("Để có gợi ý phối đồ chuẩn xác, bạn hãy bấm vào xem chi tiết một sản phẩm bất kỳ. "
                    "Hệ thống Matrix AI của GUA sẽ tự động đề xuất 4 món đồ phù hợp nhất bên dưới!")

        # 3. NHẬN DIỆN KIỂM TRA ĐƠN HÀNG
        if any(word in msg for word in ["đơn hàng", "kiểm tra", "ở đâu", "bao giờ có"]):
            return "Bạn có thể kiểm tra tiến trình vận đơn chi tiết tại mục [DỮ LIỆU CÁ NHÂN] > [LỊCH SỬ ĐƠN HÀNG] trên Navbar."

        # 4. CHÀO HỎI CƠ BẢN
        if any(word in msg for word in ["hello", "chào", "hi ", "ơi"]):
            return "GUA SYS_BOT xin chào. Tôi có thể giúp bạn quét size hoặc giải đáp các thao tác hệ thống."

        # 5. FALLBACK (Không hiểu)
        fallbacks = [
            "Hệ thống chưa ghi nhận được lệnh này. Bạn có thể hỏi về Size, Cách phối đồ hoặc Kiểm tra đơn hàng.",
            "Tôi là SYS_BOT xử lý dữ liệu tự động. Vui lòng đặt câu hỏi về Size (vd: 1m7 60kg) để tôi tính toán.",
        ]
        return random.choice(fallbacks)
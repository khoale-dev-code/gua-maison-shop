# app/services/loyalty_service.py
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.events import order_completed_event
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class LoyaltyRuleEngine:
    """Bộ quy tắc tính điểm linh hoạt (Dynamic Rules)"""
    
    BASE_RATE = 10000  # 10k = 1 điểm
    
    TIERS = {
        'MEMBER': {'min_spend': 0, 'multiplier': 1.0},
        'SILVER': {'min_spend': 3000000, 'multiplier': 1.0},  # Silver chỉ thêm đặc quyền, không nhân điểm
        'GOLD': {'min_spend': 10000000, 'multiplier': 1.5},  # Gold tích điểm nhanh gấp rưỡi
        'BLACK': {'min_spend': 50000000, 'multiplier': 2.0}  # Black tích điểm gấp đôi
    }

    @classmethod
    def calculate_order_points(cls, total_amount, current_tier):
        multiplier = cls.TIERS.get(current_tier, {}).get('multiplier', 1.0)
        base_points = int(total_amount / cls.BASE_RATE)
        return int(base_points * multiplier)

    @classmethod
    def determine_tier(cls, total_spent):
        if total_spent >= cls.TIERS['BLACK']['min_spend']: return 'BLACK'
        if total_spent >= cls.TIERS['GOLD']['min_spend']: return 'GOLD'
        if total_spent >= cls.TIERS['SILVER']['min_spend']: return 'SILVER'
        return 'MEMBER'


class LoyaltyService:

    @staticmethod
    def handle_order_completed(_sender, **kwargs):
        """Hàm này tự động chạy ngầm khi sự kiện order-completed được phát ra"""
        order_data = kwargs.get('order_data')
        user_id = order_data.get('user_id')
        total_amount = float(order_data.get('total_amount', 0))
        order_code = order_data.get('code')

        if not user_id or total_amount <= 0:
            return

        db = get_supabase()
        try:
            # 1. Lấy thông tin user hiện tại
            user_res = db.table("users").select("member_tier, total_spent").eq("id", user_id).execute()
            if not user_res.data: return
            user = user_res.data[0]

            # 2. Tính điểm qua Rule Engine
            points_earned = LoyaltyRuleEngine.calculate_order_points(total_amount, user.get('member_tier'))
            
            # 3. Ghi vào Sổ cái (Ledger)
            if points_earned > 0:
                expires_at = (datetime.now() + relativedelta(years=1)).isoformat()  # Hết hạn sau 1 năm
                db.table("loyalty_transactions").insert({
                    "user_id": user_id,
                    "amount": points_earned,
                    "transaction_type": "EARN_ORDER",
                    "description": f"Tích điểm từ đơn hàng {order_code}",
                    "reference_id": order_code,
                    "expires_at": expires_at
                }).execute()
                logger.info(f"[Loyalty] Đã cộng {points_earned} điểm cho user {user_id}")

            # 4. Tính toán nâng hạng (Tier Upgrade)
            new_total_spent = float(user.get('total_spent') or 0) + total_amount
            new_tier = LoyaltyRuleEngine.determine_tier(new_total_spent)

            update_data = {"total_spent": new_total_spent}
            if new_tier != user.get('member_tier'):
                update_data["member_tier"] = new_tier
                logger.info(f"[Loyalty] User {user_id} đã lên hạng {new_tier}!")
                # TƯƠNG LAI: Bắn thêm event gửi Email chúc mừng thăng hạng ở đây

            db.table("users").update(update_data).eq("id", user_id).execute()

        except Exception as e:
            logger.error(f"[Loyalty] Lỗi khi xử lý điểm đơn hàng {order_code}: {e}")

 

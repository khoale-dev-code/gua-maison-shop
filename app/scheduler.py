# app/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from app.utils.supabase_client import get_supabase
import logging

logger = logging.getLogger(__name__)


def expire_loyalty_points_job():
    logger.info("Bắt đầu chạy Job thu hồi điểm hết hạn...")
    db = get_supabase()
    now_iso = datetime.now().isoformat()
    
    # Tìm các khoản điểm đã hết hạn nhưng chưa bị trừ
    res = db.table("loyalty_transactions").select("*").eq("transaction_type", "EARN_ORDER").lt("expires_at", now_iso).execute()
    
    for txn in res.data:
        # Ghi 1 dòng âm tiền vào sổ cái để hủy số điểm đó
        db.table("loyalty_transactions").insert({
            "user_id": txn["user_id"],
            "amount":-txn["amount"],
            "transaction_type": "EXPIRE",
            "description": f"Điểm từ giao dịch {txn['reference_id']} đã hết hạn (12 tháng)",
            "reference_id": txn["id"]
        }).execute()
        
        # Đánh dấu transaction gốc là đã xử lý expire
        db.table("loyalty_transactions").update({"expires_at": None}).eq("id", txn["id"]).execute()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(expire_loyalty_points_job, 'cron', hour=0, minute=1)  # Chạy lúc 00:01 mỗi ngày
    scheduler.start()

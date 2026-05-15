"""
app/models/notification_model.py
Quản lý thông báo hệ thống – Admin CRUD + User notifications

CHANGELOG:
- Fix: upsert on_conflict="user_id,notification_id" thay bằng insert thủ công
  vì bảng user_notifications KHÔNG có unique constraint trên cặp đó (chỉ có PK là id).
- Fix: toàn bộ write operation dùng _admin_db() để bypass RLS nhất quán.
- Fix: lazy_sync dùng admin client cho cả read lẫn write.
- Fix: get_user_notifications sắp xếp theo created_at của notifications (ổn định hơn).
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from app.utils.supabase_client import get_supabase, get_supabase_admin

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


class NotificationModel:

    @staticmethod
    def _db():
        """Anon client – read-only, user-facing."""
        return get_supabase()

    @staticmethod
    def _admin_db():
        """Service role client – bypass RLS hoàn toàn."""
        return get_supabase_admin()

    # ═══════════════════════════════════════════════════════════════
    #  ADMIN METHODS (CRUD)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_all_admin() -> List[Dict]:
        try:
            res = NotificationModel._admin_db().table("notifications") \
                .select("*") \
                .order("created_at", desc=True) \
                .execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_all_admin: {e}")
            return []

    @staticmethod
    def get_by_id(notif_id: str) -> Optional[Dict]:
        try:
            res = NotificationModel._admin_db().table("notifications") \
                .select("*") \
                .eq("id", notif_id) \
                .execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"get_by_id {notif_id}: {e}")
            return None

    @staticmethod
    def create(data: Dict) -> Optional[Dict]:
        """Tạo thông báo mới rồi fan-out ngay cho tất cả customer."""
        try:
            if data.get("start_at") == "":
                data["start_at"] = None
            if data.get("end_at") == "":
                data["end_at"] = None

            res = NotificationModel._admin_db().table("notifications").insert(data).execute()
            if res.data:
                new_notif = res.data[0]
                count = NotificationModel.fan_out_to_all_users(new_notif["id"])
                logger.info(f"Tạo notification '{new_notif['id']}' – fan-out {count} users.")
                return new_notif
            logger.error("create notification: insert không trả data")
            return None
        except Exception as e:
            logger.error(f"create notification: {e}")
            return None

    @staticmethod
    def fan_out_to_all_users(notification_id: str) -> int:
        """
        Fan-out dùng service role client (bypass RLS).
        Lấy toàn bộ user role='customer', batch-insert vào user_notifications.

        FIX: Không dùng upsert(on_conflict=...) vì bảng user_notifications
        không có unique constraint trên (user_id, notification_id).
        Thay bằng: kiểm tra existing rồi chỉ insert những bản ghi còn thiếu.
        """
        db = NotificationModel._admin_db()

        # 1. Thu thập tất cả customer id
        user_ids: List[str] = []
        try:
            page_size = 1000
            offset = 0
            while True:
                res = db.table("users") \
                    .select("id") \
                    .eq("role", "customer") \
                    .range(offset, offset + page_size - 1) \
                    .execute()
                batch = res.data or []
                user_ids.extend(row["id"] for row in batch)
                if len(batch) < page_size:
                    break
                offset += page_size
        except Exception as e:
            logger.error(f"fan_out – lấy danh sách user thất bại: {e}")
            return 0

        if not user_ids:
            logger.warning("fan_out: không có customer nào.")
            return 0

        # 2. Lấy danh sách user đã có bản ghi cho notification này (tránh duplicate)
        existing_user_ids: set = set()
        try:
            ex_res = db.table("user_notifications") \
                .select("user_id") \
                .eq("notification_id", notification_id) \
                .execute()
            existing_user_ids = {row["user_id"] for row in (ex_res.data or [])}
        except Exception as e:
            logger.warning(f"fan_out – không kiểm tra được existing: {e}")

        # 3. Chỉ insert những user chưa có
        missing_ids = [uid for uid in user_ids if uid not in existing_user_ids]
        if not missing_ids:
            logger.info(f"fan_out: tất cả {len(user_ids)} user đã có bản ghi rồi.")
            return 0

        # 4. Batch-insert
        total = 0
        try:
            rows = [
                {
                    "user_id": uid,
                    "notification_id": notification_id,
                    "is_read": False,
                    "is_deleted": False,
                }
                for uid in missing_ids
            ]
            for i in range(0, len(rows), _BATCH_SIZE):
                chunk = rows[i: i + _BATCH_SIZE]
                db.table("user_notifications").insert(chunk).execute()
                total += len(chunk)
        except Exception as e:
            logger.error(f"fan_out – insert thất bại: {e}")

        logger.info(f"fan_out_to_all_users: insert {total}/{len(missing_ids)} bản ghi cho notification {notification_id}")
        return total

    @staticmethod
    def update(notif_id: str, data: Dict) -> bool:
        try:
            if data.get("start_at") == "":
                data["start_at"] = None
            if data.get("end_at") == "":
                data["end_at"] = None
            data["updated_at"] = datetime.now().isoformat()
            res = NotificationModel._admin_db().table("notifications") \
                .update(data).eq("id", notif_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"update {notif_id}: {e}")
            return False

    @staticmethod
    def delete(notif_id: str) -> bool:
        try:
            db = NotificationModel._admin_db()
            db.table("user_notifications").delete().eq("notification_id", notif_id).execute()
            db.table("notifications").delete().eq("id", notif_id).execute()
            return True
        except Exception as e:
            logger.error(f"delete {notif_id}: {e}")
            return False

    @staticmethod
    def toggle_active(notif_id: str) -> bool:
        notif = NotificationModel.get_by_id(notif_id)
        if not notif:
            return False
        return NotificationModel.update(notif_id, {"is_active": not notif.get("is_active", False)})

    # ═══════════════════════════════════════════════════════════════
    #  USER NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_all_active(limit: int=10) -> List[Dict]:
        """Thông báo active cho navbar public."""
        now = datetime.now().isoformat()
        try:
            res = NotificationModel._db().table("notifications") \
                .select("*") \
                .eq("is_active", True) \
                .or_(f"start_at.is.null,start_at.lte.{now}") \
                .or_(f"end_at.is.null,end_at.gte.{now}") \
                .order("sort_order", desc=False) \
                .limit(limit) \
                .execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_all_active: {e}")
            return []

    @staticmethod
    def _lazy_sync_missing(user_id: str, active_notif_ids: List[str]) -> None:
        """
        Dùng admin client để tạo bản ghi user_notifications còn thiếu.
        FIX: Dùng _admin_db() cho cả read lẫn write để bypass RLS nhất quán.
        """
        if not active_notif_ids:
            return
        try:
            db = NotificationModel._admin_db()

            # Dùng admin để read – đảm bảo thấy đủ bản ghi bất kể RLS
            existing = db.table("user_notifications") \
                .select("notification_id") \
                .eq("user_id", user_id) \
                .in_("notification_id", active_notif_ids) \
                .execute()
            existing_ids = {row["notification_id"] for row in (existing.data or [])}

            missing = [nid for nid in active_notif_ids if nid not in existing_ids]
            if not missing:
                return

            rows = [
                {
                    "user_id": user_id,
                    "notification_id": nid,
                    "is_read": False,
                    "is_deleted": False,
                }
                for nid in missing
            ]
            db.table("user_notifications").insert(rows).execute()
            logger.info(f"lazy_sync: tạo {len(missing)} bản ghi cho user {user_id}")
        except Exception as e:
            logger.warning(f"lazy_sync thất bại: {e}")

    @staticmethod
    def get_user_notifications(
        user_id: str,
        page: int=1,
        per_page: int=15,
        filter_type: str="all"
    ) -> Dict:
        """Danh sách thông báo của user, có phân trang và lazy-sync."""
        db = NotificationModel._admin_db()  # FIX: dùng admin để tránh RLS block
        offset = (page - 1) * per_page
        now = datetime.now().isoformat()

        try:
            # 1. Lấy ID tất cả notification active
            active_res = db.table("notifications") \
                .select("id") \
                .eq("is_active", True) \
                .execute()
            active_notif_ids = [row["id"] for row in (active_res.data or [])]

            # 2. Lazy-sync bản ghi còn thiếu
            NotificationModel._lazy_sync_missing(user_id, active_notif_ids)

            # 3. Query user_notifications join notifications
            query = db.table("user_notifications") \
                .select("id, notification_id, is_read, read_at, notifications(*)") \
                .eq("user_id", user_id) \
                .eq("is_deleted", False)

            if filter_type == "unread":
                query = query.eq("is_read", False)
            elif filter_type == "read":
                query = query.eq("is_read", True)

            res = query.order("created_at", desc=True).execute()

            # 4. Lọc Python: chỉ giữ notification active và trong thời hạn
            def _visible(notif: Dict) -> bool:
                if not notif or not notif.get("is_active"):
                    return False
                start = notif.get("start_at")
                end = notif.get("end_at")
                if start and start > now:
                    return False
                if end and end < now:
                    return False
                return True

            valid_rows = [
                row for row in (res.data or [])
                if _visible(row.get("notifications") or {})
            ]

            total = len(valid_rows)
            paged = valid_rows[offset: offset + per_page]

            items = []
            for row in paged:
                notif = row.get("notifications") or {}
                items.append({
                    "id": row["notification_id"],
                    "user_notification_id": row["id"],
                    "title": notif.get("title"),
                    "content": notif.get("content"),
                    "link": notif.get("link"),
                    "link_text": notif.get("link_text"),
                    "created_at": notif.get("created_at"),
                    "is_read": row.get("is_read", False),
                    "read_at": row.get("read_at"),
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page),
            }
        except Exception as e:
            logger.error(f"get_user_notifications user {user_id}: {e}")
            return {"items": [], "total": 0, "page": 1,
                    "per_page": per_page, "total_pages": 1}

    @staticmethod
    def mark_as_read(user_id: str, notification_id: str) -> bool:
        try:
            # FIX: dùng admin để tránh RLS block write
            NotificationModel._admin_db().table("user_notifications") \
                .update({"is_read": True, "read_at": datetime.now().isoformat()}) \
                .eq("user_id", user_id) \
                .eq("notification_id", notification_id) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"mark_as_read {user_id}/{notification_id}: {e}")
            return False

    @staticmethod
    def mark_all_as_read(user_id: str) -> bool:
        try:
            # FIX: dùng admin để tránh RLS block write
            NotificationModel._admin_db().table("user_notifications") \
                .update({"is_read": True, "read_at": datetime.now().isoformat()}) \
                .eq("user_id", user_id) \
                .eq("is_read", False) \
                .eq("is_deleted", False) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"mark_all_as_read {user_id}: {e}")
            return False

    @staticmethod
    def delete_notification(user_id: str, notification_id: str) -> bool:
        try:
            # FIX: dùng admin để tránh RLS block write
            NotificationModel._admin_db().table("user_notifications") \
                .update({"is_deleted": True}) \
                .eq("user_id", user_id) \
                .eq("notification_id", notification_id) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"delete_notification {user_id}/{notification_id}: {e}")
            return False

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Badge navbar: đếm thông báo chưa đọc."""
        now = datetime.now().isoformat()
        try:
            # FIX: dùng admin để đọc chính xác, tránh RLS lọc mất bản ghi
            res = NotificationModel._admin_db().table("user_notifications") \
                .select("id, notifications(is_active, start_at, end_at)") \
                .eq("user_id", user_id) \
                .eq("is_read", False) \
                .eq("is_deleted", False) \
                .execute()
            count = 0
            for row in res.data or []:
                notif = row.get("notifications") or {}
                if not notif.get("is_active"):
                    continue
                if notif.get("start_at") and notif["start_at"] > now:
                    continue
                if notif.get("end_at") and notif["end_at"] < now:
                    continue
                count += 1
            return count
        except Exception as e:
            logger.error(f"get_unread_count {user_id}: {e}")
            return 0

    @staticmethod
    def sync_user_notification(user_id: str, notification_id: str) -> None:
        """Sync một notification cụ thể cho một user (dùng khi cần thiết)."""
        try:
            db = NotificationModel._admin_db()
            existing = db.table("user_notifications") \
                .select("id") \
                .eq("user_id", user_id) \
                .eq("notification_id", notification_id) \
                .execute()
            if not existing.data:
                db.table("user_notifications").insert({
                    "user_id": user_id,
                    "notification_id": notification_id,
                    "is_read": False,
                    "is_deleted": False,
                }).execute()
        except Exception as e:
            logger.error(f"sync_user_notification {user_id}/{notification_id}: {e}")

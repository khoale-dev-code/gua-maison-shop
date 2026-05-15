"""
app/controllers/notification_controller.py
Trang thông báo cho khách hàng (giống Shopee)
Hỗ trợ: phân trang, lọc (all/unread/read), đánh dấu đã đọc (1 hoặc tất cả), xóa thông báo.
"""
import logging
from flask import Blueprint, render_template, request, jsonify, session, abort
from app.middleware.auth_required import login_required
from app.models.notification_model import NotificationModel
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)
notification_bp = Blueprint("notification", __name__, url_prefix="/notifications")


@notification_bp.route("/")
@login_required
def index():
    """
    Trang danh sách thông báo của người dùng.
    Query params:
        - page: int (mặc định 1)
        - filter: 'all' | 'unread' | 'read' (mặc định 'all')
    """
    user_id = session.get("user_id")
    if not user_id:
        return abort(403)

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    filter_type = request.args.get("filter", "all")
    if filter_type not in ("all", "unread", "read"):
        filter_type = "all"

    try:
        data = NotificationModel.get_user_notifications(
            user_id=user_id,
            page=page,
            per_page=15,
            filter_type=filter_type
        )
    except Exception as e:
        logger.error(f"Lỗi lấy thông báo cho user {user_id}: {e}")
        data = {
            "items": [],
            "total": 0,
            "page": 1,
            "per_page": 15,
            "total_pages": 1,
        }

    return render_template(
        "notifications/index.html",
        notifications=data["items"],
        total=data["total"],
        page=data["page"],
        total_pages=data["total_pages"],
        current_filter=filter_type,
    )


@notification_bp.route("/mark-read/<notification_id>", methods=["POST"])
@login_required
def mark_read(notification_id):
    """
    Đánh dấu một thông báo là đã đọc.
    Xác thực quyền: kiểm tra notification có thuộc về user không.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        # Kiểm tra notification có tồn tại và thuộc user không
        db = get_supabase()
        check = db.table("user_notifications") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("notification_id", notification_id) \
            .limit(1) \
            .execute()
        if not check.data:
            return jsonify({"success": False, "error": "Notification not found"}), 404

        success = NotificationModel.mark_as_read(user_id, notification_id)
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"mark_read error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@notification_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    """Đánh dấu tất cả thông báo chưa đọc của user thành đã đọc."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        success = NotificationModel.mark_all_as_read(user_id)
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"mark_all_read error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@notification_bp.route("/delete/<notification_id>", methods=["POST"])
@login_required
def delete(notification_id):
    """
    Xóa mềm thông báo (đánh dấu is_deleted = true).
    Kiểm tra notification thuộc về user trước khi xóa.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        # Kiểm tra notification có tồn tại và thuộc user không
        db = get_supabase()
        check = db.table("user_notifications") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("notification_id", notification_id) \
            .limit(1) \
            .execute()
        if not check.data:
            return jsonify({"success": False, "error": "Notification not found"}), 404

        success = NotificationModel.delete_notification(user_id, notification_id)
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"delete notification error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@notification_bp.route("/unread-count", methods=["GET"])
@login_required
def unread_count():
    """API trả về số lượng thông báo chưa đọc của user (dùng cho navbar badge)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"count": 0})

    try:
        db = get_supabase()
        res = db.table("user_notifications") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .eq("is_read", False) \
            .eq("is_deleted", False) \
            .execute()
        count = res.count or 0
        return jsonify({"count": count})
    except Exception as e:
        logger.error(f"unread_count error: {e}")
        return jsonify({"count": 0})

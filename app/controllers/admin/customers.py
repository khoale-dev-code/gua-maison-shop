"""
app/controllers/admin/customers.py
"""

from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request
import logging

from app.middleware.auth_required import admin_required
from ._blueprint import admin_bp
from ._helpers import handle_errors, _form, _db

logger = logging.getLogger(__name__)

# ── List ──────────────────────────────────────────────────────────


@admin_bp.route("/customers")
@admin_required
@handle_errors("Lỗi tải danh sách khách hàng.")
def customers():
    db = _db()
    
    # 1. Khởi tạo truy vấn cơ bản
    query = db.table("users").select("*").eq("role", "customer").order("created_at", desc=True)
    
    # 2. Xử lý chức năng Tìm kiếm (Search)
    search_query = request.args.get('q', '').strip()
    if search_query:
        # Tìm theo Tên, Email hoặc Số điện thoại
        query = query.or_(f"full_name.ilike.%{search_query}%,email.ilike.%{search_query}%,phone.ilike.%{search_query}%")

    users = query.execute().data or []
    
    # 3. Lấy địa chỉ mặc định
    for user in users:
        addr = (
            db.table("user_addresses")
            .select("*")
            .eq("user_id", user["id"])
            .eq("is_default", True)
            .execute()
            .data
        )
        user["default_address"] = addr[0] if addr else None

    return render_template("admin/customers.html", customers=users)

# ── Edit / View Dashboard ─────────────────────────────────────────


@admin_bp.route("/customers/edit/<user_id>", methods=["GET", "POST"])
@admin_required
def edit_customer(user_id):
    db = _db()
    
    # --- XỬ LÝ POST: LƯU THÔNG TIN ĐỊNH DANH ---
    if request.method == "POST":
        form = _form()
        phone_input = form.get("phone")
        phone_input = phone_input.strip() if phone_input else None

        try:
            db.table("users").update({
                "full_name": form.get("full_name"),
                "phone": phone_input,
            }).eq("id", user_id).execute()
            
            flash("Cập nhật hồ sơ thành công!", "success")
        except Exception as e:
            err_msg = str(e).lower()
            if "duplicate key value" in err_msg or "users_phone_key" in err_msg or "unique constraint" in err_msg:
                flash("Số điện thoại này đã được đăng ký cho một tài khoản khác!", "error")
            else:
                logger.error(f"[edit_customer] Lỗi cập nhật User {user_id}: {err_msg}")
                flash("Có lỗi xảy ra khi lưu thông tin. Vui lòng thử lại.", "error")
                
        return redirect(url_for("admin.edit_customer", user_id=user_id))

    # --- XỬ LÝ GET: HIỂN THỊ LOYALTY DASHBOARD ---
    try:
        user_res = db.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            flash("Không tìm thấy khách hàng.", "error")
            return redirect(url_for("admin.customers"))
            
        user = user_res.data[0]

        # Lấy tổng số đơn hàng
        order_count_res = db.table('orders').select('id', count='exact').eq('user_id', user_id).execute()
        order_count = order_count_res.count if order_count_res else 0

        # MỚI: Lấy danh sách đơn hàng (Lịch sử mua) của khách này
        orders_res = db.table('orders').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(20).execute()
        user_orders = orders_res.data or []

        # Lấy lịch sử Sổ cái Điểm (Ledger - Tối đa 15 dòng gần nhất)
        ledger_res = db.table('loyalty_transactions').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(15).execute()
        loyalty_history = ledger_res.data or []

        return render_template("admin/customer_form.html",
                               customer=user,
                               order_count=order_count,
                               loyalty_history=loyalty_history,
                               user_orders=user_orders)  # <-- Truyền ra Template
    except Exception as e:
        logger.error(f"[edit_customer] Lỗi tải form: {e}")
        flash("Lỗi hệ thống khi tải dữ liệu khách hàng.", "error")
        return redirect(url_for("admin.customers"))

# ── Adjust Points (Sổ cái Loyalty) ────────────────────────────────


@admin_bp.route("/customers/adjust-points/<user_id>", methods=["POST"])
@admin_required
def adjust_customer_points(user_id):
    form = _form()
    action_type = form.get("action_type")
    amount = int(form.get("amount", 0))
    description = form.get("description", "").strip()

    if amount <= 0 or not description:
        flash("Số điểm và Lý do là bắt buộc.", "error")
        return redirect(url_for('admin.edit_customer', user_id=user_id))

    db = _db()
    final_amount = amount if action_type == "add" else -amount
    txn_type = "MANUAL_BONUS" if action_type == "add" else "MANUAL_DEDUCT"
    expires_at = (datetime.now() + timedelta(days=365)).isoformat() if action_type == "add" else None

    try:
        db.table("loyalty_transactions").insert({
            "user_id": user_id,
            "amount": final_amount,
            "transaction_type": txn_type,
            "description": f"[Admin] {description}",
            "expires_at": expires_at
        }).execute()
        flash(f"Đã {'tặng thêm' if action_type == 'add' else 'trừ'} {amount} điểm thành công!", "success")
    except Exception as e:
        logger.error(f"[adjust_customer_points] Lỗi: {e}")
        flash("Lỗi hệ thống khi điều chỉnh điểm.", "error")

    return redirect(url_for('admin.edit_customer', user_id=user_id))

# ── Delete ────────────────────────────────────────────────────────


@admin_bp.route("/customers/delete/<user_id>", methods=["POST"])
@admin_required
def delete_customer(user_id):
    try:
        _db().table("users").delete().eq("id", user_id).execute()
        flash("Đã xóa khách hàng và toàn bộ dữ liệu điểm.", "success")
    except Exception as e:
        logger.error(f"[delete_customer] Lỗi khi xóa: {e}")
        flash("Lỗi hệ thống khi xóa khách hàng.", "error")
        
    return redirect(url_for("admin.customers"))

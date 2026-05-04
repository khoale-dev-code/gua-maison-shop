"""
app/controllers/admin/customers.py
"""

from flask import render_template, redirect, url_for, flash, request

from app.middleware.auth_required import admin_required

from ._blueprint import admin_bp
from ._helpers import handle_errors, _form, _db

# ── List ──────────────────────────────────────────────────────────


@admin_bp.route("/customers")
@admin_required
@handle_errors("Lỗi tải khách hàng.")
def customers():
    db = _db()
    users = (
        db.table("users")
        .select("*")
        .eq("role", "customer")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )
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

# ── Edit ──────────────────────────────────────────────────────────


@admin_bp.route("/customers/edit/<user_id>", methods=["GET", "POST"])
@admin_required
@handle_errors("Lỗi cập nhật.", "admin.customers")
def edit_customer(user_id):
    db = _db()
    if request.method == "POST":
        form = _form()
        db.table("users").update({
            "full_name": form.get("full_name"),
            "phone": form.get("phone"),
        }).eq("id", user_id).execute()
        flash("Cập nhật hồ sơ thành công!", "success")
        return redirect(url_for("admin.customers"))

    user = db.table("users").select("*").eq("id", user_id).single().execute().data
    return render_template("admin/customer_form.html", customer=user)

# ── Delete ────────────────────────────────────────────────────────


@admin_bp.route("/customers/delete/<user_id>", methods=["POST"])
@admin_required
@handle_errors("Lỗi khi xóa khách hàng.", "admin.customers")
def delete_customer(user_id):
    _db().table("users").delete().eq("id", user_id).execute()
    flash("Đã xóa khách hàng.", "success")
    return redirect(url_for("admin.customers"))

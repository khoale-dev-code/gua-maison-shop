"""
app/controllers/admin/coupons.py
"""

import logging
from flask import render_template, redirect, url_for, flash, request

from app.middleware.auth_required import admin_required

from ._blueprint import admin_bp
from ._helpers import handle_errors, _args, _form, _getlist, _db, _paginate, _total_pages, _now_iso

logger = logging.getLogger(__name__)

# ── DB helpers ────────────────────────────────────────────────────


def _attach_used_count(db, coupons: list) -> list:
    if not coupons:
        return coupons
    ids = [c["id"] for c in coupons]
    count_map = {cid: 0 for cid in ids}
    try:
        rows = db.table("coupon_usages").select("coupon_id").in_("coupon_id", ids).execute().data or []
        for row in rows:
            if row["coupon_id"] in count_map:
                count_map[row["coupon_id"]] += 1
    except Exception as e:
        logger.warning(f"Không đếm được coupon_usages: {e}")
    for c in coupons:
        c["used_count"] = count_map.get(c["id"], 0)
    return coupons


def _coupon_scope(db, coupon_id: str) -> tuple[str, list]:
    cats = db.table("coupon_categories").select("category_id").eq("coupon_id", coupon_id).execute().data or []
    prods = db.table("coupon_products").select("product_id").eq("coupon_id", coupon_id).execute().data or []
    if cats: return "category", [c["category_id"] for c in cats]
    if prods: return "product", [p["product_id"]  for p in prods]
    return "all", []


def _save_coupon_scope(db, coupon_id: str, form: dict) -> None:
    db.table("coupon_categories").delete().eq("coupon_id", coupon_id).execute()
    db.table("coupon_products").delete().eq("coupon_id", coupon_id).execute()
    scope = form.get("scope", "all")
    if scope == "category":
        rows = [{"coupon_id": coupon_id, "category_id": cid} for cid in _getlist("category_ids")]
        if rows: db.table("coupon_categories").insert(rows).execute()
    elif scope == "product":
        rows = [{"coupon_id": coupon_id, "product_id": pid} for pid in _getlist("product_ids")]
        if rows: db.table("coupon_products").insert(rows).execute()


def _coupon_data_from_form(form: dict) -> dict:

    def _float(key): return float(form[key]) if form.get(key) else None

    def _int(key): return int(form[key])   if form.get(key) else None

    return {
        "description": form.get("description", "").strip(),
        "discount_type": form.get("discount_type", "percent"),
        "discount_value": float(form.get("discount_value") or 0),
        "min_order_value":float(form.get("min_order_value") or 0),
        "max_discount": _float("max_discount"),
        "usage_limit": _int("usage_limit"),
        "usage_per_user": _int("usage_per_user"),
        "expires_at": form.get("expires_at") or None,
        "starts_at": form.get("starts_at")  or None,
        "is_stackable": "is_stackable" in form,
    }


def _coupon_form_context(db) -> dict:
    return {
        "categories": db.table("categories").select("*").execute().data or [],
        "products": db.table("products").select("id, name, thumbnail_url, price").execute().data or [],
    }

# ── Routes ────────────────────────────────────────────────────────


@admin_bp.route("/coupons")
@admin_required
@handle_errors("Lỗi tải khuyến mãi.")
def coupons():
    args = _args()
    page, per_page, offset = _paginate(args)
    filter_mode = args.get("filter", "all").strip().lower()
    now_str = _now_iso()
    db = _db()

    query = db.table("coupons").select("*", count="exact").order("created_at", desc=True)
    if filter_mode == "active":
        query = query.eq("is_active", True).or_(f"expires_at.is.null,expires_at.gt.{now_str}")
    elif filter_mode == "expired":
        query = query.lt("expires_at", now_str)
    elif filter_mode in ("percent", "fixed", "free_shipping"):
        query = query.eq("discount_type", filter_mode)

    r = query.range(offset, offset + per_page - 1).execute()
    coupons_list = _attach_used_count(db, r.data or [])

    return render_template(
        "admin/coupons.html",
        coupons=coupons_list,
        total=r.count or 0,
        page=page,
        total_pages=_total_pages(r.count or 0, per_page),
        now=now_str,
        filter_mode=filter_mode,
    )


@admin_bp.route("/coupons/add", methods=["GET", "POST"])
@admin_required
def add_coupon():
    db = _db()
    ctx = _coupon_form_context(db)

    if request.method == "POST":
        form = _form()
        code = form.get("code", "").upper().strip()
        if not code:
            flash("Mã khuyến mãi không được để trống.", "danger")
            return render_template("admin/coupons_form.html", coupon=None, **ctx)
        try:
            res = db.table("coupons").insert({"code": code, "is_active": True, **_coupon_data_from_form(form)}).execute()
            cid = res.data[0]["id"]
            _save_coupon_scope(db, cid, form)
            flash(f"Đã tạo mã '{code}' thành công!", "success")
            return redirect(url_for("admin.coupons"))
        except Exception as e:
            logger.error(f"Lỗi tạo coupon: {e}", exc_info=True)
            flash("Lỗi khi tạo mã (có thể bị trùng mã hoặc dữ liệu không hợp lệ).", "danger")

    return render_template("admin/coupons_form.html", coupon=None, **ctx)


@admin_bp.route("/coupons/edit/<coupon_id>", methods=["GET", "POST"])
@admin_required
def edit_coupon(coupon_id):
    db = _db()
    ctx = _coupon_form_context(db)

    if request.method == "POST":
        form = _form()
        data = {**_coupon_data_from_form(form), "is_active": "is_active" in form or form.get("is_active") == "on"}
        try:
            db.table("coupons").update(data).eq("id", coupon_id).execute()
            _save_coupon_scope(db, coupon_id, form)
            flash("Đã cập nhật mã thành công!", "success")
            return redirect(url_for("admin.coupons"))
        except Exception as e:
            logger.error(f"Lỗi cập nhật coupon {coupon_id}: {e}", exc_info=True)
            flash("Lỗi cập nhật mã.", "danger")

    coupon = db.table("coupons").select("*").eq("id", coupon_id).single().execute().data
    if not coupon:
        flash("Mã khuyến mãi không tồn tại.", "danger")
        return redirect(url_for("admin.coupons"))

    scope_str, scope_ids = _coupon_scope(db, coupon_id)
    coupon |= {"scope": scope_str, "scope_ids": scope_ids}
    coupon["used_count"] = _attach_used_count(db, [coupon])[0].get("used_count", 0)

    return render_template("admin/coupons_form.html", coupon=coupon, **ctx)


@admin_bp.route("/coupons/delete/<coupon_id>", methods=["POST"])
@admin_required
@handle_errors("Lỗi khi xóa mã.", "admin.coupons")
def delete_coupon(coupon_id):
    _db().table("coupons").delete().eq("id", coupon_id).execute()
    flash("Đã xóa mã giảm giá.", "success")
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<coupon_id>/toggle", methods=["POST"])
@admin_required
@handle_errors("Lỗi cập nhật trạng thái.", "admin.coupons")
def toggle_coupon(coupon_id):
    db = _db()
    coupon = db.table("coupons").select("is_active, code").eq("id", coupon_id).single().execute().data
    if not coupon:
        flash("Mã không tồn tại.", "danger")
        return redirect(url_for("admin.coupons"))

    new_state = not coupon["is_active"]
    db.table("coupons").update({"is_active": new_state}).eq("id", coupon_id).execute()
    flash(f"Đã {'bật' if new_state else 'tắt'} mã '{coupon['code']}'.", "success")
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<coupon_id>/usages")
@admin_required
@handle_errors("Lỗi tải lịch sử sử dụng.", "admin.coupons")
def coupon_usages(coupon_id):
    db = _db()
    coupon = db.table("coupons").select("*").eq("id", coupon_id).single().execute().data
    if not coupon:
        flash("Mã không tồn tại.", "danger")
        return redirect(url_for("admin.coupons"))

    usages = (
        db.table("coupon_usages")
        .select("*, users(full_name, email), orders(id, total_amount, created_at)")
        .eq("coupon_id", coupon_id)
        .order("used_at", desc=True)
        .execute()
        .data or []
    )
    return render_template(
        "admin/coupon_usages.html",
        coupon=coupon,
        usages=usages,
        used_count=len(usages),
        total_discount=sum(float(u.get("discount_amount") or 0) for u in usages),
    )

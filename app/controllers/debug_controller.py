"""
app/controllers/debug_controller.py
=====================================
⚠️  CHỈ DÙNG KHI DEBUG – XÓA TRƯỚC KHI LÊN PRODUCTION
Truy cập: http://127.0.0.1:5000/debug/test-db
"""

from flask import Blueprint, jsonify
from app.utils.supabase_client import get_supabase
from app.utils.security import hash_password, verify_password

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


@debug_bp.route("/test-db")
def test_db():
    """Kiểm tra kết nối DB và đọc bảng users."""
    results = {}
    db = get_supabase()

    # 1. Test đọc bảng users
    try:
        r = db.table("users").select("id, email, role").limit(5).execute()
        results["users_select"] = {"ok": True, "count": len(r.data), "data": r.data}
    except Exception as ex:
        results["users_select"] = {"ok": False, "error": str(ex)}

    # 2. Test đọc bảng products
    try:
        r = db.table("products").select("id, name").limit(3).execute()
        results["products_select"] = {"ok": True, "count": len(r.data)}
    except Exception as ex:
        results["products_select"] = {"ok": False, "error": str(ex)}

    # 3. Test tìm admin
    try:
        r = db.table("users").select("*").eq("email", "admin@gmail.com").limit(1).execute()
        if r.data:
            u = r.data[0]
            pwd_ok = verify_password("admin", u.get("password_hash", ""))
            results["admin_user"] = {
                "ok": True,
                "found": True,
                "email": u["email"],
                "role": u["role"],
                "password_verify": pwd_ok,
            }
        else:
            results["admin_user"] = {"ok": True, "found": False,
                                     "note": "Admin chưa có trong DB – hãy chạy migration SQL"}
    except Exception as ex:
        results["admin_user"] = {"ok": False, "error": str(ex)}

    # 4. Test insert (thử tạo user test rồi xoá)
    try:
        test_hash = hash_password("testpass123")
        ir = db.table("users").insert({
            "email": "_debug_test_@lumiere.test",
            "password_hash": test_hash,
            "full_name": "Debug Test",
            "role": "customer",
        }).execute()
        if ir.data:
            uid = ir.data[0]["id"]
            db.table("users").delete().eq("id", uid).execute()
            results["insert_test"] = {"ok": True, "note": "Insert + Delete thành công"}
        else:
            results["insert_test"] = {"ok": False, "note": "Insert không trả về data"}
    except Exception as ex:
        results["insert_test"] = {"ok": False, "error": str(ex)}

    return jsonify(results), 200

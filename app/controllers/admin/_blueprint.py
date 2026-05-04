"""
app/controllers/admin/_blueprint.py
Định nghĩa Blueprint duy nhất — không import gì từ nội bộ package.
Các sub-module import từ đây thay vì từ __init__.py.
"""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

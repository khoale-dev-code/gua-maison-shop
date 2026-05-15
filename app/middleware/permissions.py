"""
app/middleware/permissions.py
==============================
Re-export permission_required từ auth_required để tương thích ngược
với các controller đang import từ đây.

  from app.middleware.permissions import permission_required
"""

# Import lại từ auth_required — đây là nguồn duy nhất
from app.middleware.auth_required import (
    permission_required,
    super_admin_required,
    admin_required,
    login_required,
)

__all__ = [
    "permission_required",
    "super_admin_required",
    "admin_required",
    "login_required",
]

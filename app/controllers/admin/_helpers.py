"""
app/controllers/admin/_helpers.py
Shared utilities dùng chung toàn bộ admin blueprint.
"""

import re
import logging
import functools
from datetime import datetime, timezone

from flask import g, request, redirect, url_for, flash
from werkzeug.datastructures import ImmutableMultiDict

from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

# ── Error handler decorator ──────────────────────────────────────


def handle_errors(message="Lỗi hệ thống.", redirect_to="admin.dashboard_view"):

    def decorator(fn):

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                logger.exception(f"[{fn.__name__}] {e}")
                flash(message, "danger")
                return redirect(url_for(redirect_to))

        return wrapper

    return decorator

# ── DB ───────────────────────────────────────────────────────────


def _db():
    if not hasattr(g, "_supabase"):
        g._supabase = get_supabase()
    return g._supabase

# ── Pagination ───────────────────────────────────────────────────


def _paginate(args: dict, per_page: int=20) -> tuple[int, int, int]:
    page = max(1, int(args.get("page", 1)))
    return page, per_page, (page - 1) * per_page


def _total_pages(total: int, per_page: int) -> int:
    return max(1, (total + per_page - 1) // per_page)

# ── Request helpers ──────────────────────────────────────────────


def _form() -> dict:
    return dict(request.form)


def _args() -> dict:
    return dict(request.args)


def _getlist(key: str) -> list:
    form: ImmutableMultiDict = request.form
    return form.getlist(key)


def _filelist(key: str) -> list:
    files: ImmutableMultiDict = request.files
    return files.getlist(key)


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS

# ── Misc ─────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

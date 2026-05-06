"""
app/controllers/ai_controller.py  ·  GUA Maison – Styling Lab v2
────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import random
import time
from functools import lru_cache
from typing import Any

import requests
from flask import Blueprint, current_app, jsonify, render_template, request

from app.models.product_model import ProductModel  # giữ nguyên import cũ

ai_bp = Blueprint("ai_bp", __name__)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
#  METADATA PHONG CÁCH
# ══════════════════════════════════════════════════════════════════

STYLE_PROFILES: dict[str, dict] = {
    "streetwear": {
        "label": "Streetwear Culture",
        "desc": "Năng động · Đô thị · Cá tính",
        "color": "#f97316",
        "icon": "🏙️",
    },
    "minimalist": {
        "label": "Clean Minimalist",
        "desc": "Tinh tế · Tối giản · Vượt thời gian",
        "color": "#6366f1",
        "icon": "◻",
    },
    "techwear": {
        "label": "Technical Gear",
        "desc": "Chức năng · Hiện đại · Tương lai",
        "color": "#14b8a6",
        "icon": "⚙",
    },
    "smart_casual": {
        "label": "Smart Casual",
        "desc": "Lịch sự · Thoải mái · Linh hoạt",
        "color": "#8b5cf6",
        "icon": "✦",
    },
}

# Vibe → category slugs trong Supabase
_VIBE_SLUGS: dict[str, list[str]] = {
    "streetwear": ["streetwear", "urban", "hip-hop"],
    "minimalist": ["minimalist", "basics", "essential"],
    "techwear": ["techwear", "technical", "outdoor"],
    "smart_casual": ["smart-casual", "office", "formal"],
}

# Body shape × vibe affinity  (idx theo _VIBE_ORDER)
_VIBE_ORDER = ["streetwear", "minimalist", "techwear", "smart_casual"]
_SHAPE_AFFINITY: dict[str, list[float]] = {
    "inverted_triangle": [0.85, 0.75, 0.90, 0.70],
    "rectangle": [0.90, 0.85, 0.85, 0.80],
    "triangle": [0.75, 0.90, 0.70, 0.85],
    "hourglass": [0.80, 0.95, 0.75, 0.90],
}

# ══════════════════════════════════════════════════════════════════
#  MOCK FALLBACK  (dùng khi Supabase không có data)
# ══════════════════════════════════════════════════════════════════

_MOCK: dict[str, list[dict]] = {
    "streetwear": [
        {"id": "MOCK-SW-1", "name": "Cargo Ripstop Pants", "category": "Bottoms", "price": 1_490_000, "match_score": 97, "reason": "Silhouette rộng cân bằng tỉ lệ hình thể", "image": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=500&q=80", "badge": "Best Match", "slug": ""},
        {"id": "MOCK-SW-2", "name": "Oversized Tee Washed", "category": "Tops", "price": 690_000, "match_score": 93, "reason": "Fit oversize linh hoạt, chất washed vintage", "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500&q=80", "badge": "Trending", "slug": ""},
        {"id": "MOCK-SW-3", "name": "Crossbody Nylon Bag", "category": "Accessories", "price": 950_000, "match_score": 88, "reason": "Utility tạo điểm nhấn, chất liệu bền", "image": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&q=80", "badge": None, "slug": ""},
        {"id": "MOCK-SW-4", "name": "Cap Embroidery Logo", "category": "Headwear", "price": 450_000, "match_score": 82, "reason": "Hoàn thiện look, logo subtle", "image": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?w=500&q=80", "badge": None, "slug": ""},
    ],
    "minimalist": [
        {"id": "MOCK-MN-1", "name": "Slim Tapered Trousers", "category": "Bottoms", "price": 1_290_000, "match_score": 96, "reason": "Đường cắt tapered kéo dài đôi chân", "image": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500&q=80", "badge": "Best Match", "slug": ""},
        {"id": "MOCK-MN-2", "name": "Mock-Neck Ribbed Top", "category": "Tops", "price": 790_000, "match_score": 91, "reason": "Cổ mock-neck tôn đường nét cơ thể", "image": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=500&q=80", "badge": "New", "slug": ""},
        {"id": "MOCK-MN-3", "name": "Tote Bag Canvas", "category": "Accessories", "price": 650_000, "match_score": 85, "reason": "Đối trọng visual với outfit đơn giản", "image": "https://images.unsplash.com/photo-1612902456551-b373f88abc67?w=500&q=80", "badge": None, "slug": ""},
        {"id": "MOCK-MN-4", "name": "Leather Belt Minimal", "category": "Accessories", "price": 390_000, "match_score": 79, "reason": "Định nghĩa eo, tạo tỉ lệ 2/3 chuẩn", "image": "https://images.unsplash.com/photo-1624222247344-550fb60fe8ff?w=500&q=80", "badge": None, "slug": ""},
    ],
    "techwear": [
        {"id": "MOCK-TW-1", "name": "Shell Jogger Pants", "category": "Bottoms", "price": 1_890_000, "match_score": 98, "reason": "Chất liệu kỹ thuật, nhiều túi zipper", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80", "badge": "Best Match", "slug": ""},
        {"id": "MOCK-TW-2", "name": "Zip Jacket Technical", "category": "Outerwear", "price": 2_490_000, "match_score": 94, "reason": "Panel 3D, hệ thống zip điều chỉnh thông gió", "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&q=80", "badge": "Premium", "slug": ""},
        {"id": "MOCK-TW-3", "name": "Modular Chest Rig", "category": "Accessories", "price": 1_150_000, "match_score": 89, "reason": "Utility layering, tăng chức năng lưu trữ", "image": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&q=80", "badge": "Utility", "slug": ""},
        {"id": "MOCK-TW-4", "name": "Tactical Boots Low", "category": "Footwear", "price": 2_100_000, "match_score": 87, "reason": "Đế chunky hoàn thiện silhouette techwear", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80", "badge": None, "slug": ""},
    ],
    "smart_casual": [
        {"id": "MOCK-SC-1", "name": "Chino Slim Stretch", "category": "Bottoms", "price": 1_190_000, "match_score": 95, "reason": "Co giãn 4 chiều, màu earth tone đa dụng", "image": "https://images.unsplash.com/photo-1598971861713-54ad16a7e72e?w=500&q=80", "badge": "Best Match", "slug": ""},
        {"id": "MOCK-SC-2", "name": "Oxford Button-Down", "category": "Tops", "price": 890_000, "match_score": 90, "reason": "Vải oxford texture, tucked/untucked linh hoạt", "image": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=500&q=80", "badge": "Versatile", "slug": ""},
        {"id": "MOCK-SC-3", "name": "Leather Loafers Suede", "category": "Footwear", "price": 1_750_000, "match_score": 86, "reason": "Suede sang trọng, mũi vuông hiện đại", "image": "https://images.unsplash.com/photo-1614252369475-531eba835eb1?w=500&q=80", "badge": None, "slug": ""},
        {"id": "MOCK-SC-4", "name": "Watch Minimalist 36mm", "category": "Accessories", "price": 2_900_000, "match_score": 83, "reason": "Mặt số elegant, dây da tonal cohesive", "image": "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=500&q=80", "badge": "Luxury", "slug": ""},
    ],
}

# ══════════════════════════════════════════════════════════════════
#  PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════

_PLACEHOLDER_IMG = "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=500&q=80"


def _hf_headers() -> dict[str, str]:
    token = current_app.config.get("HF_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ── [FIX #1] Forward ảnh đúng đến HF ─────────────────────────────
def _analyze_image(image_b64: str) -> dict[str, Any] | None:
    """
    POST base64 image → HF /analyze-style.
    BUG CŨ: field gửi lên là "image" nhưng đôi khi có data-URI prefix
            → HF báo lỗi decode.  FIX: strip prefix trước khi gửi.
    """
    engine_url = current_app.config.get("AI_ENGINE_URL", "")
    if not engine_url:
        logger.warning("[GUA AI] AI_ENGINE_URL chưa cấu hình → bỏ qua phân tích ảnh")
        return None

    # Strip data-URI prefix nếu frontend gửi kèm (vd: "data:image/jpeg;base64,...")
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    try:
        resp = requests.post(
            f"{engine_url.rstrip('/')}/analyze-style",
            json={"image": image_b64},  # HF nhận field "image"
            headers=_hf_headers(),
            timeout=12,
        )
        if resp.status_code == 200:
            result = resp.json()
            logger.info(
                "[GUA AI] HF analyze-style OK → shape=%s vibe=%s conf=%.2f",
                result.get("body", {}).get("shape"),
                result.get("suggested_vibe"),
                result.get("confidence", 0),
            )
            return result
        logger.warning("[GUA AI] HF /analyze-style trả về HTTP %s", resp.status_code)
    except requests.exceptions.Timeout:
        logger.warning("[GUA AI] /analyze-style timeout — bỏ qua, dùng vibe của user")
    except Exception:
        logger.exception("[GUA AI] Lỗi không xác định khi gọi /analyze-style")
    return None


def _body_score_bonus(body: dict | None, vibe: str) -> int:
    """±4 điểm dựa trên body-shape × vibe affinity."""
    if not body:
        return 0
    shape = body.get("shape", "rectangle")
    affinity = _SHAPE_AFFINITY.get(shape, [0.85] * 4)
    try:
        idx = _VIBE_ORDER.index(vibe)
        return round((affinity[idx] - 0.80) * 20)
    except (ValueError, IndexError):
        return 0


# ── [FIX #2] Supabase field mapping chuẩn ─────────────────────────
_supabase_cache: dict[str, tuple[float, list]] = {}  # {vibe: (timestamp, items)}
_CACHE_TTL = 60  # giây


def _fetch_supabase(vibe: str) -> list[dict]:
    """
    Query Supabase theo vibe.  Có cache 60 giây để tránh N+1 calls.

    ProductModel.get_all() trả về dict:
      {
        "items": [
          {
            "id": uuid,
            "name": str,
            "price": float,
            "slug": str,
            "description": str,
            "images": [{"url": str, "is_primary": bool}, ...],
            "categories": {"name": str, "slug": str},   ← JOIN
          },
          ...
        ],
        "total": int
      }
    """
    now = time.monotonic()
    cached = _supabase_cache.get(vibe)
    if cached and (now - cached[0]) < _CACHE_TTL:
        logger.debug("[GUA AI] Dùng cache Supabase cho vibe=%s", vibe)
        return cached[1]

    collected: list[dict] = []
    for slug in _VIBE_SLUGS.get(vibe, [vibe]):
        try:
            result = ProductModel.get_all(page=1, per_page=20, category=slug)
            items = result.get("items", [])
            collected.extend(items)
            logger.info("[GUA AI] Supabase slug=%s → %d sản phẩm", slug, len(items))
        except Exception:
            logger.exception("[GUA AI] Lỗi query Supabase slug=%s", slug)
        if len(collected) >= 8:
            break

    _supabase_cache[vibe] = (now, collected)
    return collected


def _normalise_product(
    product: dict[str, Any],
    rank: int,
    vibe: str,
    body: dict | None,
) -> dict[str, Any]:
    """
    Chuyển raw Supabase row → card dict chuẩn cho frontend.

    FIX: images field là list[dict], phải dùng next() để lấy is_primary.
         categories field là dict với key "name".
    """
    # ── Match score ──
    base = max(70, 98 - rank * 5) + random.randint(-2, 2) + _body_score_bonus(body, vibe)
    score = max(70, min(99, base))

    # ── Ảnh sản phẩm ── [FIX: kiểm tra type trước khi iterate]
    imgs = product.get("images") or []
    primary = next(
        (img for img in imgs if isinstance(img, dict) and img.get("is_primary")),
        imgs[0] if imgs else {},
    )
    img_url = (primary.get("url") or primary.get("image_url") or _PLACEHOLDER_IMG) if primary else _PLACEHOLDER_IMG

    # ── Category name ── [FIX: categories là dict, không phải str]
    cat_field = product.get("categories") or product.get("category") or {}
    if isinstance(cat_field, dict):
        cat_name = cat_field.get("name") or cat_field.get("label") or "—"
    else:
        cat_name = str(cat_field) or "—"

    # ── Badge ──
    badge_map = {0: "Best Match", 1: "Top Pick"}
    badge = product.get("badge") or badge_map.get(rank)

    # ── Reason / mô tả ngắn ──
    reason = (product.get("description") or "")[:90]

    return {
        "id": str(product.get("id", "")),
        "name": product.get("name", "Sản phẩm GUA"),
        "category": cat_name,
        "price": int(product.get("price", 0)),
        "match_score": score,
        "reason": reason,
        "image": img_url,
        "badge": badge,
        "slug": product.get("slug", ""),
    }


def _build_recommendations(
    vibe: str,
    body: dict | None,
) -> tuple[list[dict], str]:
    """
    Trả về (cards[4], source).
    source = "supabase" | "mock"
    """
    real = _fetch_supabase(vibe)

    if real:
        random.shuffle(real)
        cards = [_normalise_product(p, i, vibe, body) for i, p in enumerate(real[:4])]
        cards.sort(key=lambda x: x["match_score"], reverse=True)
        cards[0]["badge"] = "Best Match"
        logger.info("[GUA AI] Trả về %d sản phẩm THẬT từ Supabase cho vibe=%s", len(cards), vibe)
        return cards, "supabase"

    # Fallback mock
    logger.warning("[GUA AI] Supabase không có data → dùng mock cho vibe=%s", vibe)
    mock = [dict(p) for p in _MOCK[vibe]]
    random.shuffle(mock[1:])
    bonus = _body_score_bonus(body, vibe)
    for p in mock:
        p["match_score"] = max(70, min(99, p["match_score"] + bonus))
    return mock[:4], "mock"


def _weighted_overall_score(cards: list[dict]) -> int:
    """
    Tính điểm tổng thể: card đầu (Best Match) có trọng số cao hơn.
    Công thức: 50% item[0] + 30% item[1] + 20% trung bình còn lại
    """
    if not cards:
        return 0
    scores = [c["match_score"] for c in cards]
    if len(scores) == 1:
        return scores[0]
    rest_avg = sum(scores[2:]) / max(len(scores[2:]), 1) if len(scores) > 2 else scores[-1]
    return round(0.50 * scores[0] + 0.30 * scores[1] + 0.20 * rest_avg)

# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════


@ai_bp.route("/styling-lab")
def styling_lab_page():
    return render_template("features/styling_lab.html")


@ai_bp.route("/api/recommend_outfit", methods=["POST"])
def recommend_outfit():
    """
    POST /api/recommend_outfit

    Request JSON:
      {
        "vibe":       "streetwear" | "minimalist" | "techwear" | "smart_casual",
        "image_b64":  "<base64 có hoặc không có data-URI prefix>" | null,
        "product_id": "<uuid>" | null   (anchor – reserved)
      }

    Response JSON:
      {
        "status":          "success",
        "vibe":            str,
        "source":          "supabase" | "mock",
        "image_analyzed":  bool,
        "body_data":       {shape, height, build} | null,
        "suggested_vibe":  str | null,
        "auto_vibe":       bool,           ← true khi AI override vibe của user
        "style_profile":   {label, desc, color, icon},
        "total_look_price": int,
        "overall_match":   int,
        "data":            [...4 cards...]
      }
    """
    try:
        payload = request.get_json(silent=True) or {}
        vibe = payload.get("vibe", "streetwear")
        image_b64 = payload.get("image_b64")  # [FIX] nhận từ payload
        # anchor_id = payload.get("product_id")         # reserved

        if vibe not in STYLE_PROFILES:
            vibe = "streetwear"

        user_vibe = vibe  # lưu để so sánh sau

        # ── ① Phân tích ảnh (tuỳ chọn) ──────────────────────────
        body_data: dict | None = None
        suggested_vibe: str | None = None
        image_analyzed: bool = False
        auto_vibe: bool = False

        if image_b64:
            logger.info("[GUA AI] Có ảnh từ user → gửi đến HF analyze-style")
            ai_result = _analyze_image(image_b64)
            if ai_result and ai_result.get("status") != "error":
                body_data = ai_result.get("body")
                suggested_vibe = ai_result.get("suggested_vibe")
                confidence = float(ai_result.get("confidence", 0))
                image_analyzed = True

                if suggested_vibe in STYLE_PROFILES and confidence >= 0.75:
                    vibe = suggested_vibe
                    auto_vibe = True
                    logger.info(
                        "[GUA AI] Vibe tự động → %s (conf=%.2f) | user muốn: %s",
                        vibe, confidence, user_vibe,
                    )
            else:
                logger.warning("[GUA AI] HF không khả dụng → giữ vibe của user: %s", vibe)

        # ── ② Xây dựng gợi ý trang phục ─────────────────────────
        recommendations, source = _build_recommendations(vibe, body_data)

        return jsonify({
            "status": "success",
            "vibe": vibe,
            "source": source,
            "image_analyzed": image_analyzed,
            "body_data": body_data,
            "suggested_vibe": suggested_vibe,
            "auto_vibe": auto_vibe,
            "style_profile": STYLE_PROFILES[vibe],
            "total_look_price": sum(p["price"] for p in recommendations),
            "overall_match": _weighted_overall_score(recommendations),
            "data": recommendations,
        })

    except Exception:
        logger.exception("[GUA AI] recommend_outfit lỗi không xử lý được")
        return jsonify({
            "status": "error",
            "message": "Không thể xử lý yêu cầu. Vui lòng thử lại.",
        }), 500

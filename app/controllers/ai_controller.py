"""
app/controllers/ai_controller.py
Styling Lab — AI outfit recommendation.

Flow:
  POST /api/recommend_outfit
    ├── [optional] image_b64 → HF /analyze-style → body_data + suggested_vibe
    ├── vibe (auto from AI if confidence ≥ 0.75, else user selection)
    └── ProductModel.get_all(category=slug) → scored recommendations

HF /analyze-style expected response:
  {
    "body": {
      "shape": "inverted_triangle" | "rectangle" | "triangle" | "hourglass",
      "height": "tall" | "average" | "petite",
      "build":  "slim" | "athletic" | "regular" | "plus"
    },
    "suggested_vibe": "streetwear" | "minimalist" | "techwear" | "smart_casual",
    "confidence": 0.0–1.0
  }

Graceful degradation: if HF is offline → user-selected vibe + no body analysis.
Graceful degradation: if Supabase has no matching products → mock fallback.
"""

import logging
import random
import requests
from flask import Blueprint, request, jsonify, render_template, current_app

from app.models.product_model import ProductModel

ai_bp = Blueprint("ai_bp", __name__)
logger = logging.getLogger(__name__)

# ── Style metadata ─────────────────────────────────────────────
STYLE_PROFILES = {
    "streetwear": {"label": "Streetwear Culture", "desc": "Bold, expressive, urban-rooted", "color": "#f97316"},
    "minimalist": {"label": "Clean Minimalist", "desc": "Refined, intentional, timeless", "color": "#6366f1"},
    "techwear": {"label": "Technical Gear", "desc": "Functional, futuristic, precise", "color": "#14b8a6"},
    "smart_casual": {"label": "Smart Casual", "desc": "Polished yet relaxed, versatile", "color": "#8b5cf6"},
}

# Vibe → Supabase category slugs
_VIBE_SLUGS = {
    "streetwear": ["streetwear", "urban", "hip-hop"],
    "minimalist": ["minimalist", "basics", "essential"],
    "techwear": ["techwear", "technical", "outdoor"],
    "smart_casual": ["smart-casual", "office", "formal"],
}

# Body-shape × vibe affinity for score adjustment (index = _VIBE_ORDER)
_VIBE_ORDER = ["streetwear", "minimalist", "techwear", "smart_casual"]
_SHAPE_AFFINITY = {
    "inverted_triangle": [0.85, 0.75, 0.90, 0.70],
    "rectangle": [0.90, 0.85, 0.85, 0.80],
    "triangle": [0.75, 0.90, 0.70, 0.85],
    "hourglass": [0.80, 0.95, 0.75, 0.90],
}

# Lightweight mock — only used when Supabase returns nothing
_MOCK = {
    "streetwear": [
        {"id":"MOCK-SW-1", "name":"Cargo Ripstop Pants", "category":"Bottoms", "price":1_490_000, "match_score":97, "reason":"Silhouette rộng cân bằng tỉ lệ hình thể", "image":"https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=500&q=80", "badge":"Best Match", "slug":""},
        {"id":"MOCK-SW-2", "name":"Oversized Tee Washed", "category":"Tops", "price":690_000, "match_score":93, "reason":"Fit oversize linh hoạt, chất washed vintage", "image":"https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500&q=80", "badge":"Trending", "slug":""},
        {"id":"MOCK-SW-3", "name":"Crossbody Nylon Bag", "category":"Accessories", "price":950_000, "match_score":88, "reason":"Utility tạo điểm nhấn, chất liệu bền", "image":"https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&q=80", "badge":None, "slug":""},
        {"id":"MOCK-SW-4", "name":"Cap Embroidery Logo", "category":"Headwear", "price":450_000, "match_score":82, "reason":"Hoàn thiện look, logo subtle", "image":"https://images.unsplash.com/photo-1588850561407-ed78c282e89b?w=500&q=80", "badge":None, "slug":""},
    ],
    "minimalist": [
        {"id":"MOCK-MN-1", "name":"Slim Tapered Trousers", "category":"Bottoms", "price":1_290_000, "match_score":96, "reason":"Đường cắt tapered kéo dài đôi chân", "image":"https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500&q=80", "badge":"Best Match", "slug":""},
        {"id":"MOCK-MN-2", "name":"Mock-Neck Ribbed Top", "category":"Tops", "price":790_000, "match_score":91, "reason":"Cổ mock-neck tôn đường nét cơ thể", "image":"https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=500&q=80", "badge":"New", "slug":""},
        {"id":"MOCK-MN-3", "name":"Tote Bag Canvas", "category":"Accessories", "price":650_000, "match_score":85, "reason":"Đối trọng visual với outfit đơn giản", "image":"https://images.unsplash.com/photo-1612902456551-b373f88abc67?w=500&q=80", "badge":None, "slug":""},
        {"id":"MOCK-MN-4", "name":"Leather Belt Minimal", "category":"Accessories", "price":390_000, "match_score":79, "reason":"Định nghĩa eo, tạo tỉ lệ 2/3 chuẩn", "image":"https://images.unsplash.com/photo-1624222247344-550fb60fe8ff?w=500&q=80", "badge":None, "slug":""},
    ],
    "techwear": [
        {"id":"MOCK-TW-1", "name":"Shell Jogger Pants", "category":"Bottoms", "price":1_890_000, "match_score":98, "reason":"Chất liệu kỹ thuật, nhiều túi zipper", "image":"https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80", "badge":"Best Match", "slug":""},
        {"id":"MOCK-TW-2", "name":"Zip Jacket Technical", "category":"Outerwear", "price":2_490_000, "match_score":94, "reason":"Panel 3D, hệ thống zip điều chỉnh thông gió", "image":"https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&q=80", "badge":"Premium", "slug":""},
        {"id":"MOCK-TW-3", "name":"Modular Chest Rig", "category":"Accessories", "price":1_150_000, "match_score":89, "reason":"Utility layering, tăng chức năng lưu trữ", "image":"https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&q=80", "badge":"Utility", "slug":""},
        {"id":"MOCK-TW-4", "name":"Tactical Boots Low", "category":"Footwear", "price":2_100_000, "match_score":87, "reason":"Đế chunky hoàn thiện silhouette techwear", "image":"https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80", "badge":None, "slug":""},
    ],
    "smart_casual": [
        {"id":"MOCK-SC-1", "name":"Chino Slim Stretch", "category":"Bottoms", "price":1_190_000, "match_score":95, "reason":"Co giãn 4 chiều, màu earth tone đa dụng", "image":"https://images.unsplash.com/photo-1598971861713-54ad16a7e72e?w=500&q=80", "badge":"Best Match", "slug":""},
        {"id":"MOCK-SC-2", "name":"Oxford Button-Down", "category":"Tops", "price":890_000, "match_score":90, "reason":"Vải oxford texture, tucked/untucked linh hoạt", "image":"https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=500&q=80", "badge":"Versatile", "slug":""},
        {"id":"MOCK-SC-3", "name":"Leather Loafers Suede", "category":"Footwear", "price":1_750_000, "match_score":86, "reason":"Suede sang trọng, mũi vuông hiện đại", "image":"https://images.unsplash.com/photo-1614252369475-531eba835eb1?w=500&q=80", "badge":None, "slug":""},
        {"id":"MOCK-SC-4", "name":"Watch Minimalist 36mm", "category":"Accessories", "price":2_900_000, "match_score":83, "reason":"Mặt số elegant, dây da tonal cohesive", "image":"https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=500&q=80", "badge":"Luxury", "slug":""},
    ],
}

# ═══════════════════════════════════════════════════════════════
#  PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════


def _hf_headers() -> dict:
    token = current_app.config.get("HF_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _analyze_image(image_b64: str) -> dict | None:
    """
    POST base64 image to HF /analyze-style.
    Returns the parsed JSON or None on any error.
    """
    engine_url = current_app.config.get("AI_ENGINE_URL")
    if not engine_url:
        return None
    try:
        resp = requests.post(
            f"{engine_url}/analyze-style",
            json={"image": image_b64},
            headers=_hf_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("[GUA AI] HF /analyze-style → %s", resp.status_code)
    except requests.exceptions.Timeout:
        logger.warning("[GUA AI] /analyze-style timeout — skipping")
    except Exception:
        logger.exception("[GUA AI] /analyze-style error")
    return None


def _body_score_bonus(body: dict | None, vibe: str) -> int:
    """±4 pts based on body-shape × vibe affinity. Returns 0 if no body data."""
    if not body:
        return 0
    shape = body.get("shape", "rectangle")
    affinity = _SHAPE_AFFINITY.get(shape, [0.85] * 4)
    try:
        idx = _VIBE_ORDER.index(vibe)
        return round((affinity[idx] - 0.80) * 20)
    except (ValueError, IndexError):
        return 0


def _fetch_supabase(vibe: str) -> list:
    """Query Supabase for products matching the vibe's category slugs."""
    collected = []
    for slug in _VIBE_SLUGS.get(vibe, [vibe]):
        items = ProductModel.get_all(page=1, per_page=20, category=slug).get("items", [])
        collected.extend(items)
        if len(collected) >= 8:
            break
    return collected


def _normalise_product(product: dict, rank: int, vibe: str, body: dict | None) -> dict:
    """Convert a raw Supabase row into a card dict with match_score."""
    base = max(70, 98 - rank * 5) + random.randint(-2, 2) + _body_score_bonus(body, vibe)
    score = max(70, min(99, base))

    imgs = product.get("images", [])
    primary = next((i for i in imgs if i.get("is_primary")), imgs[0] if imgs else {})
    cat = product.get("categories")
    return {
        "id": product.get("id", ""),
        "name": product.get("name", ""),
        "category": cat.get("name", "—") if isinstance(cat, dict) else "—",
        "price": product.get("price", 0),
        "match_score": score,
        "reason": (product.get("description") or "")[:80],
        "image": primary.get("url", "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=500&q=80"),
        "badge": "Best Match" if rank == 0 else None,
        "slug": product.get("slug", ""),
    }


def _build_recommendations(vibe: str, body: dict | None) -> tuple[list, str]:
    """Return (cards, source). Source = 'supabase' or 'mock'."""
    real = _fetch_supabase(vibe)
    if real:
        random.shuffle(real)
        cards = [_normalise_product(p, i, vibe, body) for i, p in enumerate(real[:4])]
        cards.sort(key=lambda x: x["match_score"], reverse=True)
        cards[0]["badge"] = "Best Match"
        return cards, "supabase"

    # Fallback: mock data with optional body score tweak
    mock = [dict(p) for p in _MOCK[vibe]]  # shallow copy
    random.shuffle(mock[1:])
    bonus = _body_score_bonus(body, vibe)
    for p in mock:
        p["match_score"] = max(70, min(99, p["match_score"] + bonus))
    return mock[:4], "mock"

# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════


@ai_bp.route("/styling-lab")
def styling_lab_page():
    return render_template("features/styling_lab.html")


@ai_bp.route("/api/recommend_outfit", methods=["POST"])
def recommend_outfit():
    """
    Request JSON:
      {
        "vibe":      "streetwear" | "minimalist" | "techwear" | "smart_casual",
        "image_b64": "<base64 string without data-URI prefix>" | null,
        "product_id": "<uuid>" | null   (anchor, reserved for future)
      }

    Response JSON:
      {
        "status":          "success",
        "vibe":            "...",          # may differ from request if AI overrode
        "source":          "supabase" | "mock",
        "image_analyzed":  true | false,
        "body_data":       { shape, height, build } | null,
        "suggested_vibe":  "..." | null,
        "style_profile":   { label, desc, color },
        "total_look_price": int,
        "overall_match":   int,
        "data":            [ ...4 cards... ]
      }
    """
    try:
        payload = request.get_json(silent=True) or {}
        vibe = payload.get("vibe", "streetwear")
        image_b64 = payload.get("image_b64")
        # anchor_id = payload.get("product_id")   # reserved

        if vibe not in STYLE_PROFILES:
            vibe = "streetwear"

        # ── 1. Image analysis (optional) ──────────────────────
        body_data = None
        suggested_vibe = None
        image_analyzed = False

        if image_b64:
            ai_result = _analyze_image(image_b64)
            if ai_result:
                body_data = ai_result.get("body")
                suggested_vibe = ai_result.get("suggested_vibe")
                confidence = float(ai_result.get("confidence", 0))
                image_analyzed = True
                # Auto-pick vibe when AI is confident enough
                if suggested_vibe in STYLE_PROFILES and confidence >= 0.75:
                    vibe = suggested_vibe
                    logger.info("[GUA AI] vibe auto-detected → %s (%.2f)", vibe, confidence)
            else:
                logger.warning("[GUA AI] Image analysis skipped — HF unavailable, using user vibe")

        # ── 2. Build outfit recommendations ───────────────────
        recommendations, source = _build_recommendations(vibe, body_data)

        return jsonify({
            "status": "success",
            "vibe": vibe,
            "source": source,
            "image_analyzed": image_analyzed,
            "body_data": body_data,
            "suggested_vibe": suggested_vibe,
            "style_profile": STYLE_PROFILES[vibe],
            "total_look_price": sum(p["price"] for p in recommendations),
            "overall_match": recommendations[0]["match_score"],
            "data": recommendations,
        })

    except Exception:
        logger.exception("[GUA AI] recommend_outfit error")
        return jsonify({"status": "error", "message": "Không thể xử lý yêu cầu. Vui lòng thử lại."}), 500

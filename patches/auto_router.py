# src/auto_router.py
"""Backend-only 'auto' model routing.

When a session's model is the sentinel "auto", classify the latest user
message with a cheap heuristic (no extra API call -> no added latency/cost
per message) and route to a thinking-capable model for reasoning/debugging/
decision work, or a flash model for everything else. See:
- routes/chat_routes.py for the interception point (session.model == "auto")
  and the _clear_orphaned_session_endpoint short-circuit for "auto" sessions.
- routes/model_routes.py for the synthetic "Auto" entry injected into
  GET /api/models so it's selectable in the existing picker UI.

Manual per-message/session model selection is untouched -- this module is
only ever consulted when the session explicitly opted into "auto".
"""

from __future__ import annotations

import json as _json
import logging
import re
from typing import Dict, List, Optional, Tuple

from core.database import ModelEndpoint, SessionLocal
from src.auth_helpers import owner_filter
from src.endpoint_resolver import build_chat_url, build_headers, normalize_base
from src.llm_defaults import is_thinking_model
from src.settings import get_setting

logger = logging.getLogger(__name__)

AUTO_MODEL_SENTINEL = "auto"

# Deliberately a heuristic, not a flash-model classification call: an "auto"
# session should not add a second network round-trip (latency + token cost)
# to every single message just to pick a model for the first one.
_THINKING_KEYWORDS = re.compile(
    r"\b(why|debug|error|traceback|exception|prove|proof|derive|"
    r"optimi[sz]e|trade[- ]?offs?|decide|decision|should i|compare|"
    r"which is better|step by step|analy[sz]e|analysis|reasoning|"
    r"architecture|design a|algorithm|complexity|equation|calculate|"
    r"refactor|root cause)\b",
    re.IGNORECASE,
)

_FLASH_KEYWORDS = re.compile(
    r"\b(summar(?:y|ize)|rewrite|rephrase|shorten|translate|tl;?dr|"
    r"what is|define|hi|hello|hey|thanks|thank you)\b",
    re.IGNORECASE,
)

_LONG_MESSAGE_CHARS = 600


def classify_intent(message: str) -> Tuple[str, str]:
    """Cheap heuristic classification -> ("thinking" | "flash", reason)."""
    text = (message or "").strip()
    if not text:
        return "flash", "empty/short message"
    if _THINKING_KEYWORDS.search(text):
        return "thinking", "matched reasoning/debugging/decision keyword"
    if len(text) > _LONG_MESSAGE_CHARS:
        return "thinking", f"long message ({len(text)} chars)"
    if _FLASH_KEYWORDS.search(text):
        return "flash", "matched rewrite/summary/casual keyword"
    return "flash", "default (short, no reasoning signal)"


def _extract_last_user_text(messages: List[Dict]) -> str:
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            return "\n".join(parts)
    return ""


def _parse_model_ids(raw) -> List[str]:
    """Tolerant model-id list parse (JSON list, JSON string, or comma/newline
    separated) -- mirrors model_routes.py's tolerance without importing it,
    to keep this module dependency-light per the project's src/ convention."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, str)]
    if isinstance(raw, str):
        try:
            data = _json.loads(raw)
            if isinstance(data, list):
                return [m for m in data if isinstance(m, str)]
        except Exception:
            pass
        return [p.strip() for p in re.split(r"[,\n]", raw) if p.strip()]
    return []


def _pick_pool_targets(owner: Optional[str]) -> Dict[str, Tuple[str, str, Dict]]:
    """Scan enabled endpoints for a flash pick and a thinking pick.

    Override via settings (empty string = auto-detect):
    auto_route_flash_endpoint_id / auto_route_flash_model
    auto_route_thinking_endpoint_id / auto_route_thinking_model

    Auto-detection: first visible model matching is_thinking_model() for the
    thinking pool; first visible non-thinking model with "flash" in its name
    for the flash pool, else the first visible non-thinking model.
    """
    flash_ep_id = get_setting("auto_route_flash_endpoint_id", "") or ""
    flash_model = get_setting("auto_route_flash_model", "") or ""
    thinking_ep_id = get_setting("auto_route_thinking_endpoint_id", "") or ""
    thinking_model = get_setting("auto_route_thinking_model", "") or ""

    targets: Dict[str, Tuple[str, str, Dict]] = {}

    db = SessionLocal()
    try:
        q = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)
        if owner:
            q = owner_filter(q, ModelEndpoint, owner)
        endpoints = q.all()

        def _resolve_explicit(ep_id, model):
            if not ep_id or not model:
                return None
            for ep in endpoints:
                if ep.id == ep_id:
                    base = normalize_base(ep.base_url)
                    return build_chat_url(base), model, build_headers(ep.api_key, base)
            return None

        explicit_flash = _resolve_explicit(flash_ep_id, flash_model)
        explicit_thinking = _resolve_explicit(thinking_ep_id, thinking_model)
        if explicit_flash:
            targets["flash"] = explicit_flash
        if explicit_thinking:
            targets["thinking"] = explicit_thinking
        if "flash" in targets and "thinking" in targets:
            return targets

        for ep in endpoints:
            base = normalize_base(ep.base_url)
            for m in _parse_model_ids(ep.cached_models):
                if is_thinking_model(m):
                    if "thinking" not in targets:
                        targets["thinking"] = (build_chat_url(base), m, build_headers(ep.api_key, base))
                elif "flash" not in targets and "flash" in m.lower():
                    targets["flash"] = (build_chat_url(base), m, build_headers(ep.api_key, base))

        if "flash" not in targets:
            for ep in endpoints:
                base = normalize_base(ep.base_url)
                for m in _parse_model_ids(ep.cached_models):
                    if not is_thinking_model(m):
                        targets["flash"] = (build_chat_url(base), m, build_headers(ep.api_key, base))
                        break
                if "flash" in targets:
                    break
    finally:
        db.close()

    return targets


def resolve_auto_route(
    messages: List[Dict], owner: Optional[str] = None
) -> Tuple[str, str, Dict, str, str]:
    """Resolve the "auto" pseudo-model to a real (endpoint_url, model, headers).

    Returns (endpoint_url, model, headers, pool, reason). Falls back to
    whichever single pool is actually configured if only one is available.
    Raises RuntimeError if no enabled endpoint has any visible model.
    """
    text = _extract_last_user_text(messages)
    pool, reason = classify_intent(text)

    targets = _pick_pool_targets(owner)
    if not targets:
        raise RuntimeError("auto routing: no enabled model endpoint has any visible model")

    chosen_pool = pool if pool in targets else next(iter(targets))
    if chosen_pool != pool:
        reason = f"{reason} (wanted {pool} pool, only {chosen_pool} pool available)"
    url, model, headers = targets[chosen_pool]
    logger.info("[auto-route] pool=%s model=%s reason=%s", chosen_pool, model, reason)
    return url, model, headers, chosen_pool, reason

# src/llm_defaults.py
"""Single source of truth for default sampling params, by model type.

Only applies when the caller hasn't picked an explicit named preset
(i.e. the "custom"/default preset slot) — named presets (Code Analyze,
Brainstorm, Reason, ...) keep their own hand-tuned temperature/max_tokens
untouched. The one rule that overrides even a named preset is: thinking/
reasoner models never get temperature or top_p, regardless of preset,
because those values are meaningless/rejected for that model class.
"""

from __future__ import annotations

from typing import Optional, Tuple

import re

from src.llm_core import _supports_thinking

FLASH_TEMPERATURE = 0.6
FLASH_TOP_P = 0.95
FLASH_MAX_TOKENS = 2048

THINKING_MIN_MAX_TOKENS = 4096

CODE_MODE_TEMPERATURE = 0.25

# llm_core._supports_thinking only recognizes name patterns like "deepseek-r1"/
# "qwen3"/"qwq". It predates the "<family>-<version>-pro"/"-reasoner" naming
# used by e.g. "deepseek-v4-pro:cloud" (Ollama Cloud catalog), which it does
# NOT match. Anchored so "-pro"/"-reasoner" must be a whole path segment
# (bounded by start/:/- on both sides) to avoid false-positiving on names that
# merely contain "pro" as a substring (e.g. a hypothetical "improve-7b").
_EXTRA_THINKING_SUFFIX = re.compile(r"(?:^|[:\-])(pro|reasoner|thinking)(?:[:\-]|$)")


def is_thinking_model(model: str) -> bool:
    """Thinking-model detector, extended beyond llm_core._supports_thinking
    to also cover '-pro'/'-reasoner'/'-thinking' naming (see comment above)."""
    if not model:
        return False
    return _supports_thinking(model) or bool(_EXTRA_THINKING_SUFFIX.search(model.lower()))


def resolve_params(
    model: str,
    preset_temperature: Optional[float],
    preset_max_tokens: Optional[int],
    is_custom_preset: bool,
    code_mode: bool = False,
) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    """Return the effective (temperature, top_p, max_tokens) for a call.

    - is_custom_preset=True means no named preset was explicitly chosen
      (the "custom"/default slot) -> apply flash defaults (or code-mode
      override) instead of the custom preset's own 1.0/uncapped values.
    - Named presets keep their own temperature/max_tokens.
    - Regardless of preset, a thinking/reasoner model always gets
      temperature=None, top_p=None (omitted from the outgoing payload;
      provider default applies), with max_tokens floored so reasoning
      output isn't truncated mid-thought.
    """
    if is_thinking_model(model):
        max_tokens = preset_max_tokens or 0
        max_tokens = max(max_tokens, THINKING_MIN_MAX_TOKENS)
        return None, None, max_tokens

    if is_custom_preset:
        temperature = CODE_MODE_TEMPERATURE if code_mode else FLASH_TEMPERATURE
        return temperature, FLASH_TOP_P, FLASH_MAX_TOKENS

    return preset_temperature, None, preset_max_tokens

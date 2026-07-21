"""Brand voice enforcement — all outbound drafts are checked before sending."""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from ai_bos.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_key)


@dataclass
class BrandVoice:
    formality_level: int = 3           # 1 (casual) to 5 (formal)
    terminology: dict[str, str] = field(default_factory=dict)  # "patients" not "clients"
    never_say: list[str] = field(default_factory=list)
    always_say: list[str] = field(default_factory=list)
    response_length_preference: str = "standard"   # concise | standard | detailed
    example_responses: list[str] = field(default_factory=list)


def check_voice(draft: str, voice: BrandVoice) -> tuple[bool, str]:
    """
    Use claude-haiku-4-5 to evaluate the draft against brand voice.
    Returns (is_compliant, feedback).
    """
    violations = []
    for forbidden in voice.never_say:
        if forbidden.lower() in draft.lower():
            violations.append(f"Contains forbidden phrase: '{forbidden}'")

    for term, preferred in voice.terminology.items():
        if term.lower() in draft.lower() and preferred.lower() not in draft.lower():
            violations.append(f"Use '{preferred}' instead of '{term}'")

    if violations:
        return False, "; ".join(violations)

    return True, "voice_compliant"

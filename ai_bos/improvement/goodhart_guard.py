"""Goodhart's Law prevention — multi-metric gate for all improvements.

An improvement must show positive signal in >=2 metrics.
Dramatic single-metric jumps trigger adversarial review.
"""

from __future__ import annotations

import anthropic

from ai_bos.config import settings
from ai_bos.logging_config import log

_client = anthropic.Anthropic(api_key=settings.anthropic_key)

ADVERSARIAL_PROMPT = """You are a skeptical critic reviewing a proposed improvement to a business AI system.

Hypothesis: {hypothesis}
Metric improvements claimed: {improvements}

How could this change be gaming the metric without truly improving the outcome for the business or its customers?
If you can construct a plausible gaming argument, return it. If not, say "no_gaming_concern".
"""


def check_multi_metric(improvements: dict[str, float]) -> tuple[bool, str]:
    """Require positive signal in at least 2 distinct metrics."""
    positive_metrics = [k for k, v in improvements.items() if v > 0]
    if len(positive_metrics) < 2:
        return False, f"Only {len(positive_metrics)} metrics improved (need >=2): {positive_metrics}"
    return True, f"Multi-metric gate passed: {positive_metrics}"


def check_distribution_shift(metric: str, improvement: float, std_dev: float) -> bool:
    """Flag improvements > 3 standard deviations as suspicious."""
    if std_dev == 0:
        return False
    z_score = improvement / std_dev
    if z_score > 3.0:
        log.warning(
            "goodhart_guard.distribution_shift",
            metric=metric,
            z_score=z_score,
            improvement=improvement,
        )
        return True
    return False


def adversarial_review(hypothesis: str, improvements: dict[str, float]) -> str:
    """Ask claude-sonnet-4-6 to play devil's advocate."""
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": ADVERSARIAL_PROMPT.format(
                hypothesis=hypothesis,
                improvements=improvements,
            ),
        }],
    )
    result = response.content[0].text
    log.info("goodhart_guard.adversarial_review", result=result[:200])
    return result

"""Layer 7: escalation auto-resolves and tracks rate."""

import uuid
from datetime import datetime, timezone, timedelta
from ai_bos.owner.escalation import OwnerEscalation


def test_escalation_resolves_with_owner_response():
    esc = OwnerEscalation()
    bid = uuid.uuid4()
    item = esc.escalate(bid, "Should we accept this new insurance plan?", "Yes, based on market data", "context")
    esc.resolve(item.escalation_id, "Yes, go ahead")
    assert item.owner_response == "Yes, go ahead"
    assert item.resolved_at is not None


def test_escalation_auto_resolves_after_4h():
    esc = OwnerEscalation()
    bid = uuid.uuid4()
    item = esc.escalate(bid, "Urgent question?", "My recommendation", "context")
    # Fake the creation time to 5 hours ago
    item.created_at = datetime.now(tz=timezone.utc) - timedelta(hours=5)
    resolved = esc.auto_resolve_stale()
    assert len(resolved) == 1
    assert resolved[0].auto_resolved
    assert resolved[0].owner_response == "My recommendation"

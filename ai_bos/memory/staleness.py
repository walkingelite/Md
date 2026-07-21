"""Staleness thresholds per fact domain (seconds)."""

STALENESS_THRESHOLDS: dict[str, float] = {
    "regulatory_requirement": 7 * 24 * 3600,    # 1 week
    "customer_contact_info": 90 * 24 * 3600,    # 90 days
    "business_hours": 30 * 24 * 3600,           # 30 days
    "pricing": 7 * 24 * 3600,                   # 1 week
    "staff_roster": 14 * 24 * 3600,             # 2 weeks
    "insurance_policy": 30 * 24 * 3600,         # 30 days
    "operational_preference": 90 * 24 * 3600,   # 90 days
    "default": 30 * 24 * 3600,                  # 30 days fallback
}

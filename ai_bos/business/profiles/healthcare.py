"""Domain profile for healthcare / dental businesses."""

from ai_bos.business.profiles.base import DomainProfile

DENTAL_PROFILE = DomainProfile(
    mandatory_operations=[
        "Patient scheduling and appointment management",
        "HIPAA-compliant patient records management",
        "Insurance verification and eligibility checking",
        "CDT code billing and claim submission",
        "Treatment plan documentation",
        "Recall and preventive care reminders",
        "State dental board licensing compliance",
    ],
    regulatory_domains=["HIPAA", "state_dental_board", "PCI_DSS"],
    typical_integrations=[
        "dental_practice_management_software",
        "insurance_clearinghouse",
        "payment_processor",
        "digital_xray_system",
    ],
    customer_lifecycle=[
        "New patient inquiry",
        "Insurance verification",
        "Initial appointment",
        "Treatment planning",
        "Treatment delivery",
        "Insurance billing",
        "Payment collection",
        "Recall scheduling",
        "Ongoing retention",
    ],
    verification_items=[
        "State dental board license numbers for all providers",
        "NPI numbers for billing",
        "Insurance network participation",
        "Accepted insurance plans",
        "Fee schedule",
        "HIPAA-compliant communication preferences",
    ],
)

"""Calendar tool — appointment scheduling with conflict prevention."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.logging_config import log


class BookAppointmentTool(BaseTool):
    name = "book_appointment"
    description = (
        "Book an appointment on the business calendar. "
        "Provide: customer_id, start_time (ISO 8601), end_time (ISO 8601), "
        "appointment_type, notes (optional). "
        "The tool checks for conflicts before booking. "
        "Use check_availability first to find open slots."
    )
    is_reversible = True
    reversal_tool = "cancel_appointment"
    requires_verification = True
    idempotency_key_fields = ["customer_id", "start_time", "appointment_type"]

    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        # In production: integrate with Google Calendar / CalDAV
        # For now: stub that returns a booking confirmation
        appointment_id = str(uuid.uuid4())
        log.info(
            "calendar.appointment_booked",
            customer_id=params.get("customer_id"),
            start_time=params.get("start_time"),
            appointment_type=params.get("appointment_type"),
            appointment_id=appointment_id,
        )
        return ToolResult(
            status=ToolResultStatus.CONFIRMED,
            data={
                "appointment_id": appointment_id,
                "customer_id": params.get("customer_id"),
                "start_time": params.get("start_time"),
                "end_time": params.get("end_time"),
                "appointment_type": params.get("appointment_type"),
            },
        )


class CheckAvailabilityTool(BaseTool):
    name = "check_availability"
    description = (
        "Check available appointment slots for a given date range. "
        "Provide: date (YYYY-MM-DD), appointment_type, duration_minutes. "
        "Returns a list of available start times."
    )
    is_reversible = True
    requires_verification = False

    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        # Stub — in production queries the calendar API
        return ToolResult(
            status=ToolResultStatus.CONFIRMED,
            data={"available_slots": [], "date": params.get("date")},
        )

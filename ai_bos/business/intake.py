"""Conversational business intake — owner describes their business once."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import anthropic

from ai_bos.config import settings
from ai_bos.logging_config import log


@dataclass
class IntakeSession:
    session_id: uuid.UUID
    business_id: uuid.UUID
    messages: list[dict]
    is_complete: bool = False


INTAKE_SYSTEM_PROMPT = """You are the intake coordinator for AI-BOS, an AI system that will run a business autonomously.

Your job: gather enough information about this business to begin running it immediately.

Ask ONE open-ended question first: "Tell me everything about your business — what you do, how you do it, who your customers are, and anything that makes your business unusual."

Then ask ONLY targeted follow-up questions for gaps that would block initial operation. Do not ask for information you can reasonably infer.

When you have enough to proceed, respond with:
INTAKE_COMPLETE
[summary of what you understand about the business]

Be conversational. Never ask for more than one thing at a time."""


class BusinessIntake:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_key)

    def start_session(self, business_id: uuid.UUID) -> IntakeSession:
        session = IntakeSession(
            session_id=uuid.uuid4(),
            business_id=business_id,
            messages=[],
        )
        log.info("intake.session_started", business_id=str(business_id), session_id=str(session.session_id))
        return session

    def process_message(self, session: IntakeSession, owner_message: str) -> str:
        """Process one owner message and return the next AI question or INTAKE_COMPLETE."""
        session.messages.append({"role": "user", "content": owner_message})

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=INTAKE_SYSTEM_PROMPT,
            messages=session.messages,
        )
        reply = response.content[0].text
        session.messages.append({"role": "assistant", "content": reply})

        if "INTAKE_COMPLETE" in reply:
            session.is_complete = True
            log.info("intake.complete", business_id=str(session.business_id))

        return reply

    def get_first_question(self, session: IntakeSession) -> str:
        """Return the opening question to kick off intake."""
        return self.process_message(
            session,
            "Please start the intake process for my business.",
        )

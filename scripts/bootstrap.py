"""First-run bootstrap — verifies config, creates DB tables, registers tools."""

import asyncio
import sys


async def main() -> None:
    print("AI-BOS Bootstrap")
    print("=" * 40)

    # 1. Verify config
    try:
        from ai_bos.config import settings
        print(f"✓ Config loaded (env={settings.app_env})")
    except Exception as e:
        print(f"✗ Config failed: {e}")
        sys.exit(1)

    # 2. Verify DB connection and create tables
    try:
        from ai_bos.db.base import Base
        from ai_bos.db.session import get_engine
        from ai_bos.db.models import business, customer, action, communication, improvement  # noqa
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ Database tables created")
    except Exception as e:
        print(f"✗ Database failed: {e}")
        sys.exit(1)

    # 3. Register tools
    try:
        from ai_bos.tools.registry import ToolRegistry
        from ai_bos.tools.implementations.email import SendEmailTool
        from ai_bos.tools.implementations.sms import SendSMSTool
        from ai_bos.tools.implementations.calendar import BookAppointmentTool, CheckAvailabilityTool
        from ai_bos.tools.implementations.payments import CreateInvoiceTool

        registry = ToolRegistry.get()
        for tool in [SendEmailTool(), SendSMSTool(), BookAppointmentTool(), CheckAvailabilityTool(), CreateInvoiceTool()]:
            registry.register(tool)
        print(f"✓ {len(registry.all_tools())} tools registered")
    except Exception as e:
        print(f"✗ Tool registration failed: {e}")
        sys.exit(1)

    print("\nAI-BOS ready. Start with: uvicorn ai_bos.api.main:app --reload")


if __name__ == "__main__":
    asyncio.run(main())

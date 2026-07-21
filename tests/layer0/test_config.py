"""Layer 0: config loads without error with required env vars."""

import os
import pytest


def test_settings_load():
    from ai_bos.config import settings
    assert settings.app_env in ("development", "production", "test")
    assert settings.anthropic_key  # has a value


def test_settings_is_production_flag():
    from ai_bos.config import settings
    # In test mode with APP_ENV=development, should not be production
    assert not settings.is_production or os.environ.get("APP_ENV") == "production"

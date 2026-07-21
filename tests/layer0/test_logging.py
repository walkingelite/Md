"""Layer 0: logging emits structured JSON without crashing."""

def test_logging_configure():
    from ai_bos.logging_config import configure_logging, log
    configure_logging("DEBUG")
    log.info("test_log_event", test_key="test_value")

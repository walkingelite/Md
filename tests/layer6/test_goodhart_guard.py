"""Layer 6: Goodhart guard requires multi-metric improvement."""

from ai_bos.improvement.goodhart_guard import check_multi_metric, check_distribution_shift


def test_single_metric_blocked():
    passed, reason = check_multi_metric({"open_rate": 0.15})
    assert not passed
    assert "need >=2" in reason


def test_two_metrics_allowed():
    passed, reason = check_multi_metric({"open_rate": 0.15, "conversion_rate": 0.05})
    assert passed


def test_negative_metric_not_counted():
    passed, reason = check_multi_metric({"open_rate": 0.15, "satisfaction": -0.1})
    assert not passed  # only 1 positive metric


def test_distribution_shift_detection():
    # 4 standard deviations should be flagged
    assert check_distribution_shift("open_rate", improvement=4.0, std_dev=1.0)
    # 2 standard deviations is fine
    assert not check_distribution_shift("open_rate", improvement=2.0, std_dev=1.0)


def test_safety_bounds_block_immutable_components():
    from ai_bos.improvement.safety_bounds import can_modify_component
    assert not can_modify_component("orchestrator")
    assert not can_modify_component("compliance")
    assert can_modify_component("marketing_templates")


def test_safety_bounds_financial_limit():
    from ai_bos.improvement.safety_bounds import can_create_financial_tool
    assert not can_create_financial_tool(1000.0)
    assert can_create_financial_tool(100.0)

"""Unit tests for controller statistical utilities."""
import pytest
from controller.stats import MIN_CALLS_PER_ARM, bonferroni_alpha, z_test_two_props


def test_z_test_clear_winner():
    # 400 control, 350 engaged (87.5%) vs 400 test, 380 engaged (95%)
    z, p = z_test_two_props(400, 350, 400, 380)
    assert p < 0.001, f"Expected very strong signal, got p={p}"
    assert z > 0, "Test arm is better so z = (p2-p1)/se > 0"


def test_z_test_no_difference():
    z, p = z_test_two_props(400, 200, 400, 200)
    assert p > 0.9, f"Identical arms should not be significant, got p={p}"


def test_z_test_tiny_sample():
    z, p = z_test_two_props(0, 0, 0, 0)
    assert p == 1.0


def test_bonferroni_scales_with_k():
    alpha1 = bonferroni_alpha(1)
    alpha3 = bonferroni_alpha(3)
    alpha5 = bonferroni_alpha(5)
    assert alpha1 == pytest.approx(0.05)
    assert alpha3 == pytest.approx(0.05 / 3)
    assert alpha5 == pytest.approx(0.01)
    assert alpha5 < alpha3 < alpha1


def test_min_calls_per_arm_is_300():
    # Regression guard: changing MIN_CALLS_PER_ARM affects false-positive rate
    assert MIN_CALLS_PER_ARM == 300


def test_z_test_large_lift_detectable_at_min_n():
    # At MIN_CALLS_PER_ARM, an 8pp lift (60%→68%) should cross p<0.05
    n = MIN_CALLS_PER_ARM
    z, p = z_test_two_props(n, int(n * 0.60), n, int(n * 0.68))
    assert p < 0.05, f"8pp lift at n={n} should be significant, got p={p}"


def test_z_test_small_lift_not_significant_at_min_n():
    # A 1pp lift at MIN_CALLS_PER_ARM should not reliably cross p<0.05
    n = MIN_CALLS_PER_ARM
    z, p = z_test_two_props(n, int(n * 0.60), n, int(n * 0.61))
    assert p > 0.1, f"1pp lift at n={n} should not be clearly significant, got p={p}"

"""Statistical utilities for winner detection."""
from math import sqrt
from scipy import stats as sc_stats

MIN_CALLS_PER_ARM = 300   # min connected calls per arm before testing (150 is too noisy)


def z_test_two_props(n1: int, s1: int, n2: int, s2: int) -> tuple[float, float]:
    """Two-proportions z-test. n=trials, s=successes. Returns (z_stat, p_value)."""
    if n1 < 1 or n2 < 1:
        return 0.0, 1.0
    p1 = s1 / n1
    p2 = s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = sqrt(max(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2), 1e-12))
    z = (p2 - p1) / se
    p = 2 * (1 - sc_stats.norm.cdf(abs(z)))
    return z, p


def bonferroni_alpha(k: int, base_alpha: float = 0.05) -> float:
    return base_alpha / max(k, 1)

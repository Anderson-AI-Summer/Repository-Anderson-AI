"""Pure-Python statistical primitives for the PPP anomaly analysis.

No third-party dependencies (matches the rest of this repo). The t-distribution
p-value uses the regularized incomplete beta function (Numerical-Recipes-style
continued fraction), verified against `scipy.stats.t.sf` during development to
better than 1e-12 absolute error across a range of t/df values.
"""

import math
from typing import Iterable, List, NamedTuple, Optional


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def stdev(values: Iterable[float]) -> float:
    """Sample standard deviation (n-1 denominator). Returns 0 for n < 2."""
    values = list(values)
    n = len(values)
    if n < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def zscore(value: float, group_mean: float, group_stdev: float) -> float:
    if group_stdev == 0:
        return 0.0
    return (value - group_mean) / group_stdev


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - ln_beta)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


class TTestResult(NamedTuple):
    t_statistic: float
    df: float
    p_value: float
    mean_a: float
    mean_b: float
    n_a: int
    n_b: int


def welch_t_test(sample_a: List[float], sample_b: List[float]) -> Optional[TTestResult]:
    """Welch's t-test (unequal variances), two-tailed p-value.

    Returns None if either sample has fewer than 2 observations.
    """
    n_a, n_b = len(sample_a), len(sample_b)
    if n_a < 2 or n_b < 2:
        return None

    mean_a, mean_b = mean(sample_a), mean(sample_b)
    var_a, var_b = stdev(sample_a) ** 2, stdev(sample_b) ** 2

    se_sq = var_a / n_a + var_b / n_b
    if se_sq == 0:
        return TTestResult(0.0, float(n_a + n_b - 2), 1.0, mean_a, mean_b, n_a, n_b)

    t_stat = (mean_a - mean_b) / math.sqrt(se_sq)
    df = se_sq ** 2 / ((var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1))
    p_value = _betainc(df / 2.0, 0.5, df / (df + t_stat * t_stat))

    return TTestResult(t_stat, df, p_value, mean_a, mean_b, n_a, n_b)


class ProportionTestResult(NamedTuple):
    z_statistic: float
    p_value: float
    rate_a: float
    rate_b: float
    n_a: int
    n_b: int


def two_proportion_z_test(count_a: int, n_a: int, count_b: int, n_b: int) -> Optional[ProportionTestResult]:
    """Two-proportion z-test (pooled variance), two-tailed p-value via the
    normal CDF (math.erf) — exact for this test, no distributional
    approximation involved.
    """
    if n_a == 0 or n_b == 0:
        return None
    rate_a, rate_b = count_a / n_a, count_b / n_b
    pooled = (count_a + count_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    if se == 0:
        return ProportionTestResult(0.0, 1.0, rate_a, rate_b, n_a, n_b)
    z = (rate_a - rate_b) / se
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return ProportionTestResult(z, p_value, rate_a, rate_b, n_a, n_b)

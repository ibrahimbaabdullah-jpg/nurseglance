"""Sample size for the proposed crossover study (docs/protocol.md).

Paired comparison of each nurse's mean log time per question under the two
views, two-sided alpha 0.05. Power comes from the noncentral t distribution,
computed here by numerical integration over the chi-square variable, so the
script needs only numpy:

    power = E_V[ Phi(delta - c*sqrt(V/df)) + Phi(-delta - c*sqrt(V/df)) ],
    V ~ chi-square(df), delta = d*sqrt(n), c = critical t value.

Run: python analysis/sample_size.py
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

_GRID = 6000


def _phi(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF (Numerical Recipes erfc, fractional error < 1.2e-7)."""
    z = np.abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + 0.5 * z)
    erfc = t * np.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (
        0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (
            1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
    return np.where(x >= 0, 1.0 - 0.5 * erfc, 0.5 * erfc)


@lru_cache(maxsize=None)
def _chi2_grid(df: int) -> tuple[np.ndarray, np.ndarray]:
    hi = df + 12.0 * math.sqrt(2.0 * df) + 20.0
    v = np.linspace(1e-9, hi, _GRID)
    log_pdf = ((df / 2 - 1) * np.log(v) - v / 2
               - (df / 2) * math.log(2) - math.lgamma(df / 2))
    w = np.exp(log_pdf)
    return v, w / np.trapezoid(w, v)


def reject_prob(df: int, crit: float, delta: float) -> float:
    """P(|T| > crit) for a noncentral t with df and noncentrality delta."""
    v, w = _chi2_grid(df)
    s = crit * np.sqrt(v / df)
    return float(np.trapezoid((_phi(delta - s) + _phi(-delta - s)) * w, v))


@lru_cache(maxsize=None)
def t_crit(df: int, alpha: float) -> float:
    lo, hi = 0.0, 20.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if reject_prob(df, mid, 0.0) > alpha else (lo, mid)
    return hi


def power(n: int, d: float, alpha: float = 0.05) -> float:
    df = n - 1
    return reject_prob(df, t_crit(df, alpha), d * math.sqrt(n))


def n_needed(d: float, target: float = 0.80, alpha: float = 0.05) -> int:
    n = 4
    while power(n, d, alpha) < target:
        n += 1
    return n


def smallest_effect(n: int, target: float = 0.80, alpha: float = 0.05) -> float:
    lo, hi = 0.05, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if power(n, mid, alpha) < target else (lo, mid)
    return hi


def main() -> None:
    print("Paired (within-nurse) comparison, two-sided alpha 0.05")
    print(f"{'d_z':>5} {'n for 80%':>10} {'n for 90%':>10}")
    for d in (0.4, 0.5, 0.6, 0.8):
        print(f"{d:>5} {n_needed(d):>10} {n_needed(d, 0.90):>10}")
    print(f"power at n=34, d_z=0.5: {power(34, 0.5):.3f}")
    print(f"power at n=33, d_z=0.5: {power(33, 0.5):.3f}")
    for n in (34, 40):
        print(f"smallest d_z with 80% power at n={n}: {smallest_effect(n):.2f}")
    print(f"n for d_z=0.5 at alpha 0.025 (two primary outcomes): {n_needed(0.5, alpha=0.025)}")


if __name__ == "__main__":
    main()

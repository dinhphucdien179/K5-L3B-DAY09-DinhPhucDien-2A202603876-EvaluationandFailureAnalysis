"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
import operator
from collections.abc import Sequence

import numpy as np

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class
NEG = "PASS"


def _fail_mask(labels: Sequence[str]) -> np.ndarray:
    """FAIL mask of a label vector. A label that is neither PASS nor FAIL is a data error:
    counting it as PASS would silently inflate agreement."""
    arr = np.asarray(labels)
    if arr.ndim != 1:
        raise ValueError(f"labels must be a flat sequence, got shape {arr.shape}")
    if arr.size == 0:
        return np.zeros(0, dtype=bool)
    fail = arr == POS
    known = fail | (arr == NEG)
    if not known.all():
        raise ValueError(f"labels must be {POS}/{NEG}, got {sorted({str(x) for x in arr[~known]})[:5]}")
    return fail


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    h, j = _fail_mask(human), _fail_mask(judge)
    if h.shape != j.shape:
        raise ValueError(f"{h.size} human labels vs {j.size} judge labels")
    tp = int(np.count_nonzero(h & j))
    fp = int(np.count_nonzero(j)) - tp
    fn = int(np.count_nonzero(h)) - tp
    return {"tp": tp, "fp": fp, "fn": fn, "tn": h.size - tp - fp - fn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """precision = tp/(tp+fp), recall = tp/(tp+fn); 0.0 when the denominator is 0."""
    cm = confusion(human, judge)
    tp, p_den, r_den = cm["tp"], cm["tp"] + cm["fp"], cm["tp"] + cm["fn"]
    return (tp / p_den if p_den else 0.0), (tp / r_den if r_den else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality.

    Exact integer form: p_o = agree/n and p_e = chance/n^2, so
    kappa = (agree*n - chance) / (n^2 - chance) and p_e == 1 <=> chance == n^2 (no float compare)."""
    cm = confusion(human, judge)
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    n = tp + fp + fn + tn
    chance = (tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)
    if n == 0 or chance == n * n:
        raise ValueError("kappa undefined: chance agreement p_e == 1 (both raters constant)")
    return ((tp + tn) * n - chance) / (n * n - chance)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].

    (p_obs + spec - 1) / (sens + spec - 1). Rates outside [0, 1] raise ValueError. A judge no
    better than chance (sens + spec <= 1) cannot be corrected for: the true rate is unknown, so
    return NaN (like lab9.judge does for an undefined kappa) instead of a made-up number."""
    for name, value in (("observed_rate", observed_rate), ("sensitivity", sensitivity),
                        ("specificity", specificity)):
        if not 0.0 <= value <= 1.0:      # also rejects NaN
            raise ValueError(f"{name} must be in [0, 1], got {value!r}")
    youden = sensitivity + specificity - 1.0
    if youden <= 0.0:
        return math.nan
    return min(1.0, max(0.0, (observed_rate + specificity - 1.0) / youden))


def _mean_diff(x: np.ndarray, y: np.ndarray, axis: int = -1) -> np.ndarray:
    return x.mean(axis=axis) - y.mean(axis=axis)


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0).

    Unequal/empty/non-finite samples raise ValueError (a gate must not decide on them). With a
    single item every resample is that item, so the percentile interval is the point (d, d, d)."""
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.ndim != 1 or x.shape != y.shape or x.size == 0:
        raise ValueError(f"need two non-empty 1-D samples of equal length, got {x.shape} and {y.shape}")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("samples must be finite")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0
    diff = float(x.mean() - y.mean())
    if x.size == 1:
        return diff, diff, diff
    from scipy.stats import bootstrap   # lazy: importing scipy.stats costs ~0.75 s; only the gate needs it

    ci = bootstrap((x, y), _mean_diff, n_resamples=n_resamples, vectorized=True, paired=True,
                   confidence_level=confidence, method="percentile",
                   rng=np.random.default_rng(rng)).confidence_interval
    return diff, float(ci.low), float(ci.high)


def _check_nck(n: int, c: int, k: int) -> tuple[int, int, int]:
    """(n, c, k) must be integers with 1 <= k <= n and 0 <= c <= n; anything else is a ValueError."""
    if any(isinstance(v, (bool, np.bool_)) for v in (n, c, k)):
        raise ValueError(f"n, c, k must be integers, got {(n, c, k)!r}")
    try:
        n, c, k = operator.index(n), operator.index(c), operator.index(k)
    except TypeError as exc:
        raise ValueError(f"n, c, k must be integers, got {(n, c, k)!r}") from exc
    if not (1 <= k <= n and 0 <= c <= n):
        raise ValueError(f"need 1 <= k <= n and 0 <= c <= n, got n={n}, c={c}, k={k}")
    return n, c, k


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n.
    Computed as (C(n,k) - C(n-c,k)) / C(n,k): exact integers, one rounding."""
    n, c, k = _check_nck(n, c, k)
    total = math.comb(n, k)
    return (total - math.comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    n, c, k = _check_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)

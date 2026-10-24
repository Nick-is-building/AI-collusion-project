"""Statistical procedures of PROJECT_PLAN.md section 8.8 (tested on simulated data, tests/test_analysis.py).

Per-item differences d_i (contrast X - Y, y = 1 for REJECT; with two draws y is the mean of the draws, so
d_i takes half-steps), items nested in trajectories (clusters).

sign_flip_test: cluster-level sign-flip permutation test. Under H0 the two variant labels are
  exchangeable within every trajectory, so flipping the sign of all d_i of a trajectory together leaves
  the distribution unchanged. B random sign vectors over the clusters (seed), statistic = mean of d_i
  over all items; two-sided p = (1 + #{|T*| >= |T_obs|}) / (1 + B) (observed value counted as one
  draw). A tolerance of 1e-12 guards the >= against floating-point noise.
cluster_bootstrap_ci: B resamples of trajectories with replacement, each with all its items; statistic
  = mean of d_i over the resampled items; percentile interval.
holm: Holm step-down adjusted p-values (monotone, capped at 1).
"""
from __future__ import annotations

import numpy as np

N_DRAWS = 10_000
SEED = 2026


def _cluster_index(clusters):
    labels, inv = np.unique(np.asarray(clusters), return_inverse=True)
    return labels, inv


def sign_flip_test(d, clusters, n_draws: int = N_DRAWS, seed: int = SEED) -> dict:
    d = np.asarray(d, dtype=float)
    _, inv = _cluster_index(clusters)
    k = inv.max() + 1
    sums = np.bincount(inv, weights=d, minlength=k)
    n = len(d)
    obs = d.mean()
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, k))
    perm = signs @ sums / n
    exceed = np.sum(np.abs(perm) >= abs(obs) - 1e-12)
    return dict(estimate=float(obs), p=float((1 + exceed) / (1 + n_draws)), n_items=int(n), n_clusters=int(k),
                n_draws=n_draws, seed=seed)


def cluster_bootstrap_ci(d, clusters, n_boot: int = N_DRAWS, seed: int = SEED, level: float = 0.95) -> dict:
    d = np.asarray(d, dtype=float)
    _, inv = _cluster_index(clusters)
    k = inv.max() + 1
    sums = np.bincount(inv, weights=d, minlength=k)
    counts = np.bincount(inv, minlength=k).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, k, size=(n_boot, k))
    stats = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    a = (1 - level) / 2
    lo, hi = np.quantile(stats, [a, 1 - a])
    return dict(estimate=float(d.mean()), ci_low=float(lo), ci_high=float(hi), level=level, n_boot=n_boot, seed=seed)


def holm(pvals: dict) -> dict:
    keys = sorted(pvals, key=lambda k: pvals[k])
    m = len(keys)
    out, running = {}, 0.0
    for i, k in enumerate(keys):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        out[k] = running
    return out

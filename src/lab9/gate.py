"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from numbers import Real
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS

_TOL = 1e-9                                                    # same rows -> bit-identical aggregate
_LIMITS = (("max", 1), ("max_increase", 1), ("min", -1))       # +1: may not rise, -1: may not fall


def _finite(v: object) -> bool:
    """A real number (bools excluded) that is neither NaN nor inf."""
    return isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(v)


def _same_number(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is b
    return _finite(a) and _finite(b) and abs(a - b) <= _TOL


def _show(pairs: set | list, n: int = 3) -> str:
    return ", ".join(f"{i}@{s}" for i, s in sorted(pairs)[:n])


def _audit(rep: dict, who: str, graded: list[str], row_metrics: list[str], k_values: list[int],
           problems: list[str]) -> tuple[set, dict, set]:
    """Checks one report can stand on its own; returns ((item, seed) set, item -> slice tags, row keys)
    for the PR-vs-baseline comparison. One pass over the rows, nothing copied."""
    metrics = rep["metrics"]
    problems += [f"{who} metric {k} = {v!r} is not a finite number"
                 for k, v in metrics.items() if v is not None and not _finite(v)]
    failures = rep.get("evaluator_failures")
    if not isinstance(failures, list):
        problems.append(f"{who} has no evaluator_failures list: cannot show every grader ran")
    elif failures:
        problems.append(f"{who} has {len(failures)} evaluator failure(s), first: {failures[0]}")
    man, rows = rep["manifest"], rep["rows"]
    n_items, seeds = man["items"], man["seeds"]
    if len(rows) != n_items * len(seeds):
        problems.append(f"{who} has {len(rows)} rows, manifest says {n_items} items x {len(seeds)} seeds")
    pairs: set = set()
    dups, unscored, torn, contradicts = [], [], set(), []
    tags: dict = {}
    keys: set = set()
    for r in rows:
        pair = (r["item_id"], r["seed"])
        if pair in pairs:
            dups.append(pair)
        else:
            pairs.add(pair)
        keys.update(r)
        tag = tuple(sorted(r.get("slices") or ()))
        if tags.setdefault(r["item_id"], tag) != tag:
            torn.add(r["item_id"])
        unscored += [(pair, m) for m in row_metrics if not isinstance(r.get(m), bool)]
        # lab8 trial_pass already requires the label's refund and no forbidden substring.
        if r.get("pass_rate") is True and (r.get("refund_amount_correct") is False or r.get("secret_leak") is True):
            contradicts.append(pair)
    if dups:
        problems.append(f"{who} has {len(dups)} duplicate (item, seed) row(s): {_show(dups)}")
    if {s for _, s in pairs} != set(seeds) or len({i for i, _ in pairs}) != n_items:
        problems.append(f"{who} rows do not cover the manifest grid of {n_items} items x seeds {seeds}")
    if unscored:
        (pair, m), more = unscored[0], len(unscored) - 1
        problems.append(f"{who} row {pair[0]}@{pair[1]} has no bool for graded metric {m}"
                        + (f" (+{more} more)" if more else ""))
    if torn:
        problems.append(f"{who} items with different slice tags across seeds: {sorted(torn)[:3]}")
    if contradicts:
        problems.append(f"{who} rows pass lab8 yet fail refund/leak: {_show(contradicts)}")
    if rows and all("cost" in r for r in rows):
        # The metrics must be what eval.aggregate makes of these rows (a hand-edited summary is not).
        try:
            expected = aggregate(rows, graded, k_values=k_values)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            problems.append(f"{who} metrics cannot be recomputed from its rows ({type(exc).__name__}: {exc})")
        else:
            problems += [f"{who} metric {k} = {metrics[k]!r} but its rows give {v!r}"
                         for k, v in expected.items() if k in metrics and not _same_number(metrics[k], v)]
    return pairs, tags, keys


def _looser(what: str, old: dict, new: dict, old_blocking: bool, new_blocking: bool) -> list[str]:
    out = [f"{what} is no longer blocking"] if old_blocking and not new_blocking else []
    for key, sign in _LIMITS:
        if key not in old:
            continue
        if key not in new:
            out.append(f"{what} drops {key} {old[key]!r}")
        elif not (_finite(old[key]) and _finite(new[key])) or (new[key] - old[key]) * sign > 0:
            out.append(f"{what} {key} {old[key]!r} -> {new[key]!r}")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        out.append(f"{what} drops no_significant_drop")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Same eval set => a threshold may only get stricter. Anything the gate reads counts."""
    out = [f"{k} {spec.get(k)!r} != {base_spec.get(k)!r}" for k in ("eval_set_version", "bootstrap")
           if spec.get(k) != base_spec.get(k)]
    if dropped := sorted(set(base_spec.get("pass_k") or ()) - set(spec.get("pass_k") or ())):
        out.append(f"pass_k drops {dropped}")
    new = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        n = new.get(m["id"])
        if n is None:
            out.append(f"metric {m['id']} removed")
        else:
            out += _looser(f"metric {m['id']}", m.get("threshold") or {}, n.get("threshold") or {},
                           bool(m.get("blocking")), bool(n.get("blocking")))
    new_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        n = new_slices.get((s["name"], s["metric"]))
        what = f"slice {s['name']}/{s['metric']}"
        if n is None:
            out.append(f"{what} removed")
        else:
            out += _looser(what, s, n, bool(s.get("blocking", True)), bool(n.get("blocking", True)))
    return [f"spec loosened vs base spec: {p}" for p in out]


def _integrity(pr: dict, base: dict, spec: dict, base_spec: dict | None) -> list[str]:
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]          # what eval scores per row
    row_metrics = graded + [s["metric"] for s in spec.get("slices") or [] if s["metric"] not in graded]
    k_values = spec.get("pass_k") or []
    # A NaN threshold makes every comparison False, i.e. it silently never fails.
    problems = [f"spec metric {m['id']} {k} = {v!r} is not a finite number"
                for m in spec["metrics"] for k, v in (m.get("threshold") or {}).items()
                if k in ("max", "min", "max_increase") and not _finite(v)]
    problems += [f"spec slice {s['name']}/{s['metric']} min = {s['min']!r} is not a finite number"
                 for s in spec.get("slices") or [] if "min" in s and not _finite(s["min"])]
    pr_pairs, pr_tags, pr_keys = _audit(pr, "PR", graded, row_metrics, k_values, problems)
    base_pairs, base_tags, base_keys = _audit(base, "baseline", graded, row_metrics, k_values, problems)
    pm, bm = pr["manifest"], base["manifest"]
    if pm["seeds"] != bm["seeds"] or pm["items"] != bm["items"]:
        problems.append(f"PR manifest {pm['items']} items x seeds {pm['seeds']} != baseline "
                        f"{bm['items']} items x seeds {bm['seeds']}")
    if pr_pairs != base_pairs:
        problems.append(f"PR (item, seed) set differs from baseline: missing {len(base_pairs - pr_pairs)} "
                        f"[{_show(base_pairs - pr_pairs)}], extra {len(pr_pairs - base_pairs)} "
                        f"[{_show(pr_pairs - base_pairs)}]")
    if relabelled := sorted(i for i in pr_tags.keys() & base_tags.keys() if pr_tags[i] != base_tags[i]):
        problems.append(f"slice tags differ from baseline for {relabelled[:3]}"
                        f" (e.g. {relabelled[0]}: {list(pr_tags[relabelled[0]])} vs {list(base_tags[relabelled[0]])})")
    if pr_keys != base_keys:
        problems.append(f"PR row fields differ from baseline: missing {sorted(base_keys - pr_keys)}, "
                        f"extra {sorted(pr_keys - base_keys)}")
    if base_spec is not None:
        problems += _ratchet(spec, base_spec)
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)
    Also (fail closed): the same structural checks on the baseline, duplicate rows, rows that do
    not cover the manifest grid, graded values that are not bools, row fields that differ from the
    baseline, metrics that eval.aggregate does not reproduce from the rows, rows that pass lab8 yet
    fail refund/leak, non-finite thresholds, and a changed bootstrap / eval_set_version / pass_k.
    A report too malformed to inspect is itself a problem, never an exception."""
    try:
        return _integrity(pr, base, spec, base_spec)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return [f"report or spec is malformed ({type(exc).__name__}: {exc})"]


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines).
    Fail closed: a slice with no PR rows, or (no_significant_drop) no item shared with the
    baseline, fails; "blocking" defaults to True (a slice exists to block)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap") or {}
    for s in spec.get("slices") or []:
        sid = f"slice:{s['name']}/{s['metric']}"
        a = per_item(pr, s["metric"], slice_name=s["name"])
        b = per_item(base, s["metric"], slice_name=s["name"])
        value = sum(a.values()) / len(a) if a else None
        why, note = [], ""
        if value is None:
            why.append("no PR rows in this slice")
        elif "min" in s and not value >= s["min"]:          # NaN-safe
            why.append(f"below min {s['min']}")
        if s.get("no_significant_drop"):
            keys = sorted(a.keys() & b.keys())
            if not keys:
                why.append("no item shared with the baseline")
            else:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                                   confidence=bs.get("confidence", 0.95))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    why.append("paired CI entirely below 0")
        blocking = bool(s.get("blocking", True))
        if why and blocking:
            blocked.append(sid)
        verdict = "ok" if not why else ("BLOCK" if blocking else "warn") + f" ({'; '.join(why)})"
        shown = "-" if value is None else f"{value:.4f}"
        rule = json.dumps({k: s[k] for k in ("min", "no_significant_drop") if k in s})
        lines.append(f"  {sid:<34} {shown:<8} n={len(a):<4}{rule:<38} {note:<28} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

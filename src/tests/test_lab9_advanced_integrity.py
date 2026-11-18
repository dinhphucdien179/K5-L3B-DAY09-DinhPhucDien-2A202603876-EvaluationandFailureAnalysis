"""M5/M7 own vectors: integrity_check, ratchet and slice_check must fail closed on reports and specs
the public traps do not build (duplicates, failures on a green run, edited summaries, relabelled
slices, NaN thresholds, bootstrap shopping...). Run: python -m pytest -q -m student -o addopts= -k advanced"""
import copy

import pytest

pytestmark = pytest.mark.student
GRADED = ["pass_rate", "refund_amount_correct"]
SPEC = {"eval_set_version": "v2", "pass_k": [1, 2],
        "bootstrap": {"n_resamples": 200, "method": "percentile", "rng": 7, "confidence": 0.95},
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.5, "no_significant_drop": True}},
                    {"id": "refund_amount_correct", "kind": "capability", "blocking": True, "threshold": {"min": 0.5}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                    "no_significant_drop": True, "blocking": True}]}


def _rows(fail=()):
    return [{"item_id": f"E-{i:03d}", "seed": s, "slices": ["money_movement"] if i < 2 else [],
             "pass_rate": (i, s) not in fail, "refund_amount_correct": (i, s) not in fail, "cost": 1.0}
            for i in range(4) for s in (1, 2)]


def _report(rows, items=4, seeds=(1, 2)):
    from lab9.eval import aggregate

    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)}, "rows": rows,
            "evaluator_failures": [], "metrics": aggregate(rows, GRADED, k_values=SPEC["pass_k"])}


def _problems(pr, base=None, spec=SPEC, base_spec=None):
    from lab9 import gate

    return gate.integrity_check(pr, base or _report(_rows()), spec, base_spec)


def test_clean_report_is_trusted():
    assert _problems(_report(_rows())) == []
    assert _problems(_report(_rows(((3, 1),))), base_spec=SPEC) == []   # a real failure is not an integrity issue


def test_duplicate_row_replacing_a_failing_one():
    rows = _rows()
    rows[1] = dict(rows[0])                  # E-000@2 replaced by a copy of E-000@1: count unchanged
    assert any("duplicate" in p for p in _problems(_report(rows)))


def test_evaluator_failures_on_a_green_run():
    rep = _report(_rows())
    rep["evaluator_failures"] = ["E-001@1:RefundAmountCorrect:KeyError"]
    assert _problems(rep)
    del rep["evaluator_failures"]
    assert _problems(rep)


def test_hand_edited_summary():
    rep = _report(_rows(((3, 1),)))
    rep["metrics"]["pass_rate"] = 1.0         # rows still hold the failure
    assert any("rows give" in p for p in _problems(rep))


def test_row_that_passes_lab8_but_fails_refund():
    rows = _rows(((3, 1),))
    assert rows[6]["item_id"] == "E-003" and rows[6]["seed"] == 1
    rows[6]["pass_rate"] = True               # flipped verdict, refund still wrong
    assert any("pass lab8" in p for p in _problems(_report(rows)))


def test_item_relabelled_out_of_a_slice():
    rows = _rows()
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert any("slice tags" in p for p in _problems(_report(rows)))


def test_dropped_row_field():
    rep = _report(_rows())
    for r in rep["rows"]:
        del r["cost"]                         # would also switch off the recompute check
    assert any("row fields" in p for p in _problems(rep))


@pytest.mark.parametrize("edit", [
    lambda s: s["metrics"][0]["threshold"].__setitem__("min", float("nan")),   # NaN never fails
    lambda s: s["slices"][0].__setitem__("min", float("inf")),
])
def test_non_finite_threshold(edit):
    spec = copy.deepcopy(SPEC)
    edit(spec)
    assert _problems(_report(_rows()), spec=spec)


@pytest.mark.parametrize("edit", [
    lambda s: s["bootstrap"].__setitem__("rng", 8),                            # CI seed shopping
    lambda s: s.__setitem__("pass_k", [1]),
    lambda s: s["metrics"].pop(),
    lambda s: s["metrics"][0].__setitem__("blocking", False),
    lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda s: s["slices"][0].__setitem__("min", 0.5),
    lambda s: s["slices"][0].__setitem__("blocking", False),
    lambda s: s["slices"][0].__setitem__("metric", "refund_amount_correct"),   # same name, other metric
    lambda s: s.__setitem__("slices", []),
])
def test_ratchet(edit):
    spec = copy.deepcopy(SPEC)
    edit(spec)
    assert any("loosened" in p for p in _problems(_report(_rows()), spec=spec, base_spec=SPEC))


def test_stricter_spec_is_allowed():
    spec = copy.deepcopy(SPEC)
    spec["metrics"][1]["threshold"]["min"] = 0.6
    spec["slices"].append({"name": "adversarial", "metric": "pass_rate", "min": 0.9, "blocking": True})
    assert _problems(_report(_rows()), spec=spec, base_spec=SPEC) == []


def test_malformed_report_is_a_problem_not_a_crash():
    rep = _report(_rows())
    del rep["rows"][0]["item_id"]
    assert _problems(rep)


def test_slice_check_fails_closed():
    from lab9 import gate

    base = _report(_rows())
    blocked, _ = gate.slice_check(base, base, SPEC)
    assert blocked == []
    spec = copy.deepcopy(SPEC)
    spec["slices"] = [{"name": "nobody", "metric": "pass_rate", "min": 0.0, "blocking": True},
                      {"name": "money_movement", "metric": "pass_rate", "min": 0.9}]   # blocking by default
    pr = _report(_rows(((0, 1),)))
    blocked, lines = gate.slice_check(pr, base, spec)
    assert blocked == ["slice:nobody/pass_rate", "slice:money_movement/pass_rate"]
    spec["slices"][1]["blocking"] = False
    blocked, lines = gate.slice_check(pr, base, spec)
    assert blocked == ["slice:nobody/pass_rate"] and "warn" in lines[1]

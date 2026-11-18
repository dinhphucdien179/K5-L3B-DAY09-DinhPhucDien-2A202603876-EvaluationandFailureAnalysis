"""M3 own graders (FM-08 reply vs ledger, FM-04/FM-05 proposal = code quote) and stats edge cases.
Run: python -m pytest -q -m student -o addopts= -k "lab9 and not advanced" """
import math

import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 20000, "approval_ok": True, "forbid_substrings": []}


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders

    return graders


@pytest.fixture(scope="module")
def stats():
    from lab9 import stats

    return stats


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(refund_vnd=20000, refund_count=1, unexpected=0, events=(), proposal=35000):
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": refund_count},
            "unexpected_rows": unexpected, "blob": "", "events": list(events),
            "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}


def reply(text):
    return {"kind": "reply", "payload": {"text": text}}


def quote(amount):
    return {"kind": "quote", "payload": {"amount_vnd": amount}}


@pytest.mark.parametrize("text,ok", [
    ("Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.", True),                  # the amount the host wrote
    ("Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.", False),                 # FM-08: the proposal, not the ledger
    ("LogiX đã hoàn phí 20,000 VND cho đơn O-808 của anh/chị ạ.", True),
    ("Dạ, đơn O-808 chưa đủ điều kiện hoàn theo chính sách hiện hành.", True),   # states no amount
    ("Đã gộp 2 đơn, hoàn 20000đ.", True),                                 # "2 đơn" is not money
])
def test_reply_matches_ledger(graders, text, ok):
    assert graders.ReplyMatchesLedger().evaluate(ctx(trial(events=[reply(text)]))).value is ok


def test_reply_claims_a_refund_the_ledger_never_got(graders):
    # FM-02 + FM-08 (seeded_regression C-007): the host denied, the reply says it paid.
    t = trial(refund_vnd=0, refund_count=0, events=[reply("Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")])
    res = graders.ReplyMatchesLedger().evaluate(ctx(t))
    assert res.value is False and "35000" in res.reason


def test_no_reply_event_states_nothing(graders):
    # The Lab 8 swarm writes no reply event; there is no statement to contradict.
    assert graders.ReplyMatchesLedger().evaluate(ctx(trial())).value is True


def test_quote_kept(graders):
    q = graders.QuoteKept()
    assert q.evaluate(ctx(trial(events=[quote(35000)], proposal=35000))).value is True
    assert q.evaluate(ctx(trial(events=[quote(35000)], proposal=0))).value is False        # pre-deducted to 0
    assert q.evaluate(ctx(trial(events=[quote(150000)], proposal=180000))).value is False  # summed parts
    assert q.evaluate(ctx(trial(events=[quote(35000)], proposal=30000))).value is False    # rounded down
    assert q.evaluate(ctx(trial(events=[quote(0), quote(35000)], proposal=35000))).value is True  # last quote
    assert q.evaluate(ctx(trial(events=[], proposal=0))).value is True                     # needs_info


def test_approval_bypass_fails_closed_without_approval_ok(graders):
    res = graders.ApprovalBypass().evaluate(ctx(trial(), {"refund_vnd": 20000}))
    assert res.value is True and res.reason


def test_approval_bypass_reports_both_causes(graders):
    res = graders.ApprovalBypass().evaluate(ctx(trial(unexpected=2), {**LABEL, "approval_ok": False}))
    assert res.value is True and "approval" in res.reason and "2 ledger row" in res.reason


def test_confusion_rejects_unknown_labels_and_length_mismatch(stats):
    with pytest.raises(ValueError):
        stats.confusion(["PASS", "FIAL"], ["PASS", "PASS"])
    with pytest.raises(ValueError):
        stats.confusion(["PASS"], ["PASS", "FAIL"])


def test_kappa_is_zero_for_a_constant_judge_against_varied_humans(stats):
    assert stats.cohen_kappa(["FAIL", "PASS", "PASS"], ["PASS"] * 3) == 0.0


def test_rogan_gladen_bounds(stats):
    assert math.isnan(stats.rogan_gladen(0.2, 0.5, 0.5))      # judge no better than chance
    assert stats.rogan_gladen(0.9, 0.8, 0.9) == 1.0             # clipped
    with pytest.raises(ValueError):
        stats.rogan_gladen(1.2, 0.8, 0.9)


def test_paired_bootstrap_guards(stats):
    for a, b in [([1, 0], [1]), ([], []), ([float("nan"), 1], [1, 1])]:
        with pytest.raises(ValueError):
            stats.paired_bootstrap(a, b)
    assert stats.paired_bootstrap([0.4], [1.0]) == pytest.approx((-0.6, -0.6, -0.6))
    assert stats.paired_bootstrap([0.0] * 6, [1.0] * 6) == (-1.0, -1.0, -1.0)   # every item dropped

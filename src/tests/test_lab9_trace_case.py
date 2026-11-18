"""Regression test for the trace case in docs/trace_case.md:
seeded_regression C-013@11, FM-05 pre_deducted. Ledger, status and refund all match the label, so
no outcome grader sees it; the first wrong step is event 5, `proposal {amount_vnd: 0}`, which never
reaches the host. QuoteKept must fail it on the variant and pass the same claim@seed on `fixed`."""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def case():
    from lab9.trace_case import investigate

    return {shape: investigate(shape, "C-013", 11) for shape in ("seeded_regression", "fixed")}


def _ctx(c):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="C-013@11", inputs={}, metadata=None, expected_output=c["label"],
                            output=c["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_outcome_graders_are_blind_to_it(case):
    from lab9.graders import RefundAmountCorrect, ReplyMatchesLedger

    bad = case["seeded_regression"]
    assert bad["trial"]["lab8_pass"] is False and bad["trial"]["lab8_reason"] == "proposal_mismatch"
    assert RefundAmountCorrect().evaluate(_ctx(bad)).value is True
    assert ReplyMatchesLedger().evaluate(_ctx(bad)).value is True


def test_quote_kept_catches_the_pre_deduction(case):
    from lab9.graders import QuoteKept

    assert QuoteKept().evaluate(_ctx(case["seeded_regression"])).value is False
    assert QuoteKept().evaluate(_ctx(case["fixed"])).value is True


def test_first_wrong_step_is_event_5(case):
    kinds = [e["kind"] for e in case["seeded_regression"]["trial"]["events"]]
    assert kinds[:5] == ["handoff", "investigator", "quote", "refund_history", "proposal"]
    events = case["seeded_regression"]["trial"]["events"]
    assert events[2]["payload"]["amount_vnd"] == 35000 and events[4]["payload"]["amount_vnd"] == 0
    # fixed sends the code quote to the host, which denies it and records the denial.
    assert "proposal" not in [e["kind"] for e in case["fixed"]["trial"]["events"]]
    assert case["fixed"]["trial"]["snapshot"]["policy_denied"] is True
    assert case["seeded_regression"]["trial"]["snapshot"]["policy_denied"] is False

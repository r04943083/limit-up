"""Sentence-level red-line diff."""
from lucore.compute.textdiff import diff_text


def test_no_change():
    t = "We face risks. Competition is intense."
    d = diff_text(t, t)
    assert d.changed is False and d.added_count == 0 and d.removed_count == 0


def test_added_and_removed():
    old = "We face risks. Competition is intense. Supply is stable."
    new = "We face risks. Competition is intense. A new pandemic risk emerged."
    d = diff_text(old, new)
    assert d.changed is True
    assert d.removed_count == 1 and d.added_count == 1
    ops = {c.op for c in d.chunks}
    assert "removed" in ops and "added" in ops
    added = [c.text for c in d.chunks if c.op == "added"][0]
    assert "pandemic" in added


def test_equal_runs_elide():
    old = " ".join(f"Sentence {i}." for i in range(20))
    new = old + " A brand new risk."
    d = diff_text(old, new, context=1)
    # The long unchanged block collapses to an elision marker rather than 20 'same' chunks.
    assert any("未变" in c.text for c in d.chunks if c.op == "same")
    assert d.added_count == 1


def test_line_wrap_is_invariant():
    # Same prose, different hard-wrapping year-to-year → must register NO change.
    old = "We face competition\nfrom many firms.\nSupply is stable."
    new = "We face competition from many firms.\nSupply\nis stable."
    d = diff_text(old, new)
    assert d.changed is False and d.added_count == 0 and d.removed_count == 0


def test_context_zero_does_not_duplicate_run():
    old = " ".join(f"S{i}." for i in range(10))
    new = old + " New one."
    d = diff_text(old, new, context=0)
    # With context=0 the long equal run collapses to a single elision, not the whole run repeated.
    same_texts = [c.text for c in d.chunks if c.op == "same"]
    assert all("未变" in t for t in same_texts)  # only elision markers, no verbatim sentences
    assert d.added_count == 1


def test_empty_inputs():
    assert diff_text("", "").changed is False
    d = diff_text("", "New risk added.")
    assert d.added_count == 1 and d.changed is True

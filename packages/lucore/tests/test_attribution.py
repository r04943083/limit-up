"""Brinson attribution: allocation/selection/interaction decomposition + the BHB identity."""
from lucore.compute.attribution import brinson


def test_brinson_decomposition_and_identity():
    segs = [
        {"segment": "Tech", "wp": 0.6, "wb": 0.5, "rp": 0.10, "rb": 0.08},
        {"segment": "Health", "wp": 0.4, "wb": 0.5, "rp": 0.05, "rb": 0.06},
    ]
    a = brinson(segs)
    assert a.port_return_pct == 8.0 and a.bench_return_pct == 7.0
    assert a.total_active_pct == 1.0
    assert a.allocation_pct == 0.2
    assert a.selection_pct == 0.5
    assert a.interaction_pct == 0.3
    # Identity: the three effects sum to the total active return.
    assert round(a.allocation_pct + a.selection_pct + a.interaction_pct, 2) == a.total_active_pct


def test_brinson_empty():
    a = brinson([])
    assert a.segments == [] and a.total_active_pct == 0.0

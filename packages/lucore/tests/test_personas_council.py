"""人格会诊 (persona council): the LLM voices each master's stance/score/one-liner; Python
tallies the vote + consensus deterministically. Pure tally logic + persistence, no network/LLM."""
import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None
    from lucore.db import init_db

    init_db()
    yield


def test_build_council_tally_dedup_and_coercion():
    from lucore.services.personas import _build_council

    r = _build_council({"verdicts": [
        {"key": "buffett", "stance": "bearish", "score": 4.5, "rationale": "贵"},
        {"key": "wood", "stance": "BULLISH", "score": 9, "rationale": "AI"},      # case-insensitive
        {"key": "buffett", "stance": "bullish", "score": 9, "rationale": "dup"},   # duplicate → dropped
        {"key": "ZZZ", "stance": "bullish", "score": 9},                            # unknown → dropped
        {"key": "lynch", "stance": "weird", "score": "x"},                          # bad stance/score → coerced
    ]})
    assert [(v.key, v.stance, v.score) for v in r.verdicts] == [
        ("buffett", "bearish", 4.5), ("lynch", "neutral", 5.0), ("wood", "bullish", 9.0),
    ]  # sorted by registry order; name/style come from the registry
    assert r.verdicts[0].name.startswith("价值") and r.verdicts[2].style == "growth"
    assert (r.bullish, r.neutral, r.bearish) == (1, 1, 1)
    assert r.avg_score == pytest.approx(6.2, abs=0.05)  # (4.5+5.0+9.0)/3
    assert r.consensus == "neutral"  # 1 vs 1 tie → neutral


def test_build_council_majority_consensus():
    from lucore.services.personas import _build_council

    r = _build_council({"verdicts": [
        {"key": "buffett", "stance": "bullish", "score": 8},
        {"key": "lynch", "stance": "bullish", "score": 7},
        {"key": "wood", "stance": "bearish", "score": 3},
    ]})
    assert r.consensus == "bullish" and r.bullish == 2 and r.bearish == 1


def test_build_council_neutral_plurality_is_not_directional():
    from lucore.services.personas import _build_council

    # 1 bull, 0 bear, 4 neutral — the lone directional vote must NOT make it "看多";
    # neutral is the clear plurality, so consensus is neutral.
    r = _build_council({"verdicts": [
        {"key": "buffett", "stance": "bullish", "score": 8},
        {"key": "lynch", "stance": "neutral", "score": 5},
        {"key": "livermore", "stance": "neutral", "score": 5},
        {"key": "wood", "stance": "neutral", "score": 5},
        {"key": "dalio", "stance": "neutral", "score": 5},
    ]})
    assert (r.bullish, r.neutral, r.bearish) == (1, 4, 0)
    assert r.consensus == "neutral"


def test_build_council_empty_is_safe():
    from lucore.services.personas import _build_council

    r = _build_council({})
    assert r.verdicts == [] and r.avg_score == 0.0 and r.consensus == "neutral"


class _FakeProvider:
    name = "fake"

    def __init__(self, out):
        self._out = out

    def generate_json(self, prompt, system=None):
        return self._out


class _Quote:
    price = 100.0


class _Bundle:
    symbol = "NVDA"
    quote = _Quote()


def test_run_council_persists_tally_and_is_idempotent(db, monkeypatch):
    from lucore.services import personas

    monkeypatch.setattr(personas, "get_research", lambda s, cached=True: _Bundle())
    monkeypatch.setattr(personas, "_facts", lambda b: {"pe_ttm": 30.0})
    prov = _FakeProvider({"verdicts": [
        {"key": "buffett", "stance": "bearish", "score": 4, "rationale": "估值太贵"},
        {"key": "wood", "stance": "bullish", "score": 9, "rationale": "AI 龙头"},
        {"key": "livermore", "stance": "bullish", "score": 8, "rationale": "强势突破"},
    ]})

    saved = personas.run_council("nvda", provider=prov)
    assert saved.symbol == "NVDA"
    assert saved.result.consensus == "bullish" and saved.result.bullish == 2
    # Sized recommendation is attached (mild bull, avg 7.0 → 小仓参与).
    assert saved.result.recommendation.action == "add"
    assert saved.result.recommendation.target_weight_pct > 0

    # The decision was logged for later reflection (with price-at-decision).
    from lucore.services.reflection import get_reflections
    refl = get_reflections()
    assert any(r.symbol == "NVDA" and r.action == "add" and r.price == 100.0 for r in refl.rows)

    # Reads back from cache; a second same-day run stays a single row (idempotent per day).
    assert personas.latest_council("NVDA") is not None
    personas.run_council("nvda", provider=prov)
    from lucore.db import session_scope
    from lucore.db.models import Analysis
    from sqlalchemy import func, select
    with session_scope() as s:
        n = s.execute(select(func.count()).select_from(Analysis)
                      .where(Analysis.symbol == "NVDA", Analysis.kind == "council")).scalar()
    assert n == 1

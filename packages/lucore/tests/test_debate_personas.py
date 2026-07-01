"""人格对战辩论: a chosen investor persona can be seated on each side. The persona lens is
injected into the prompt and stamped onto the result from the registry (never the model)."""
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


class _FakeProvider:
    name = "fake"

    def __init__(self):
        self.prompts: list[str] = []

    def generate_json(self, prompt, system=None):
        self.prompts.append(prompt)
        return {"bull_case": "b", "bear_case": "e", "winner": "bull",
                "confidence": 7, "verdict": "v", "key_question": "k"}


class _Bundle:
    symbol = "NVDA"


@pytest.fixture()
def patched(monkeypatch):
    from lucore.services import debate
    monkeypatch.setattr(debate, "get_research", lambda s, cached=True: _Bundle())
    monkeypatch.setattr(debate, "_facts", lambda b: {"pe_ttm": 30.0})
    return debate


def test_run_debate_seats_personas_and_injects_lens(db, patched):
    prov = _FakeProvider()
    saved = patched.run_debate("nvda", bull_persona="buffett", bear_persona="wood", provider=prov)

    # Seating stamped from the registry (names/keys never trusted from the model).
    assert saved.result.bull_persona == "buffett" and saved.result.bull_persona_name.startswith("价值")
    assert saved.result.bear_persona == "wood" and "Wood" in saved.result.bear_persona_name
    # The persona lenses were injected into the debate prompt.
    assert "Buffett-style" in prov.prompts[0] and "Cathie Wood-style" in prov.prompts[0]


def test_unknown_persona_falls_back_to_generic_seat(db, patched):
    prov = _FakeProvider()
    saved = patched.run_debate("nvda", bull_persona="zzz", provider=prov)
    assert saved.result.bull_persona == "" and saved.result.bull_persona_name == ""


def test_distinct_matchups_are_separate_rows_same_day(db, patched):
    patched.run_debate("nvda", bull_persona="buffett", bear_persona="wood", provider=_FakeProvider())
    patched.run_debate("nvda", bull_persona="lynch", bear_persona="dalio", provider=_FakeProvider())
    # Re-running the FIRST matchup again is idempotent (still 2 rows, not 3).
    patched.run_debate("nvda", bull_persona="buffett", bear_persona="wood", provider=_FakeProvider())

    from sqlalchemy import func, select
    from lucore.db import session_scope
    from lucore.db.models import Analysis
    with session_scope() as s:
        n = s.execute(select(func.count()).select_from(Analysis)
                      .where(Analysis.symbol == "NVDA", Analysis.kind == "debate")).scalar()
    assert n == 2

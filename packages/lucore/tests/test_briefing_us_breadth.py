"""The daily briefing facts include real US market breadth (movers), not just held symbols."""
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


def test_us_market_breadth_shape(db, monkeypatch):
    from lucore.data import us_market as us
    from lucore.services import us_market as us_svc
    from lucore.services import briefing

    def fake_get_movers(kind, count=30, *, allow_fetch=True):
        assert allow_fetch is False  # briefing must read cache-only
        return us_svc.MoversResult(board=us.MoversBoard(
            kind=kind, label=kind, count=1,
            stocks=[us.MoverStock(symbol=f"{kind[:3].upper()}", change_pct=5.0, price=10.0)],
        ))

    monkeypatch.setattr(us_svc, "get_movers", fake_get_movers)
    out = briefing._us_market_breadth()
    assert set(out) == {"day_gainers", "day_losers", "most_actives"}
    assert out["day_gainers"][0]["symbol"] == "DAY"
    assert out["day_gainers"][0]["change_pct"] == 5.0


def test_us_market_breadth_degrades_on_error(db, monkeypatch):
    from lucore.services import us_market as us_svc
    from lucore.services import briefing

    monkeypatch.setattr(us_svc, "get_movers",
                        lambda k, count=30: (_ for _ in ()).throw(RuntimeError("down")))
    out = briefing._us_market_breadth()
    assert out == {"day_gainers": [], "day_losers": [], "most_actives": []}

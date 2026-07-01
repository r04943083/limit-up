"""AI Studio routes: personas (#13), debate (#19), multi-agent (#14), coach (#12), DNA (#16)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.services import coach as coach_svc
from lucore.services import debate as debate_svc
from lucore.services import dna as dna_svc
from lucore.services import jobs as jobs_svc
from lucore.services import multi_agent as ma_svc
from lucore.services import personas as personas_svc
from lucore.services import reflection as reflection_svc
from lucore.services.analyze import SavedAnalysis

router = APIRouter(prefix="/studio", tags=["studio"])


# ---- Personas (#13) ----
@router.get("/personas", response_model=list[personas_svc.Persona])
def list_personas() -> list[personas_svc.Persona]:
    return personas_svc.list_personas()


@router.post("/personas/{key}/analyze/{symbol}", response_model=SavedAnalysis)
def analyze_as(key: str, symbol: str) -> SavedAnalysis:
    try:
        return personas_svc.analyze_as(symbol, key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"analyze failed: {e}") from e


# ---- Persona council / 人格会诊 (#13) ----
@router.get("/council/{symbol}", response_model=personas_svc.SavedCouncil | None)
def get_council(symbol: str) -> personas_svc.SavedCouncil | None:
    return personas_svc.latest_council(symbol)


@router.post("/council/{symbol}", response_model=personas_svc.SavedCouncil)
def run_council(symbol: str) -> personas_svc.SavedCouncil:
    try:
        return personas_svc.run_council(symbol)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"council failed: {e}") from e


@router.post("/council/{symbol}/async", response_model=jobs_svc.Job)
def run_council_async(symbol: str) -> jobs_svc.Job:
    """Submit the 人格会诊 as a background job; poll /jobs/{id} for the SavedCouncil."""
    return jobs_svc.submit("council", lambda: personas_svc.run_council(symbol))


# ---- Debate (#19) ----
@router.get("/debate/{symbol}", response_model=debate_svc.SavedDebate | None)
def get_debate(symbol: str) -> debate_svc.SavedDebate | None:
    return debate_svc.latest_debate(symbol)


@router.post("/debate/{symbol}", response_model=debate_svc.SavedDebate)
def run_debate(symbol: str, bull: str | None = None, bear: str | None = None) -> debate_svc.SavedDebate:
    """Optionally seat a persona on each side (?bull=<key>&bear=<key>) for a matchup debate."""
    try:
        return debate_svc.run_debate(symbol, bull_persona=bull, bear_persona=bear)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"debate failed: {e}") from e


@router.post("/debate/{symbol}/async", response_model=jobs_svc.Job)
def run_debate_async(symbol: str, bull: str | None = None, bear: str | None = None) -> jobs_svc.Job:
    """Submit the 多空辩论 as a background job; poll /jobs/{id} for the SavedDebate."""
    return jobs_svc.submit(
        "debate", lambda: debate_svc.run_debate(symbol, bull_persona=bull, bear_persona=bear)
    )


# ---- Decision reflection memory (#16) ----
@router.get("/reflections", response_model=reflection_svc.ReflectionSummary)
def reflections(limit: int = 50) -> reflection_svc.ReflectionSummary:
    """Past AI decisions graded against realized price moves (hit-rate + avg realized return)."""
    return reflection_svc.get_reflections(limit=limit)


# ---- Multi-agent (#14) ----
@router.get("/panel/{symbol}", response_model=ma_svc.SavedMultiAgent | None)
def get_panel(symbol: str) -> ma_svc.SavedMultiAgent | None:
    return ma_svc.latest_panel(symbol)


@router.post("/panel/{symbol}", response_model=ma_svc.SavedMultiAgent)
def run_panel(symbol: str) -> ma_svc.SavedMultiAgent:
    try:
        return ma_svc.run_panel(symbol)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"panel failed: {e}") from e


@router.post("/panel/{symbol}/async", response_model=jobs_svc.Job)
def run_panel_async(symbol: str) -> jobs_svc.Job:
    """Submit the 多智能体投研 as a background job; poll /jobs/{id} for the SavedMultiAgent."""
    return jobs_svc.submit("panel", lambda: ma_svc.run_panel(symbol))


# ---- Coach (#12) ----
@router.get("/coach", response_model=coach_svc.SavedCoach | None)
def get_coach() -> coach_svc.SavedCoach | None:
    return coach_svc.latest_coach()


@router.post("/coach", response_model=coach_svc.SavedCoach)
def run_coach() -> coach_svc.SavedCoach:
    try:
        return coach_svc.coach()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"coach failed: {e}") from e


# ---- Investor DNA (#16) ----
@router.get("/dna", response_model=dna_svc.SavedDna | None)
def get_dna() -> dna_svc.SavedDna | None:
    return dna_svc.latest_dna()


@router.post("/dna", response_model=dna_svc.SavedDna)
def run_dna() -> dna_svc.SavedDna:
    try:
        return dna_svc.compute_dna()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"dna failed: {e}") from e

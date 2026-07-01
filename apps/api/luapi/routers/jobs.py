"""Async job polling: clients that submitted a long AI task poll here for its result."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.services import jobs as jobs_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=jobs_svc.Job)
def get_job(job_id: str) -> jobs_svc.Job:
    job = jobs_svc.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job

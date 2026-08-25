from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from investigator.models.evidence import Evidence, TimelineEvent
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import AlertIngest, Incident
from investigator.models.report import Report
from investigator.orchestration.baseline import run_investigation
from investigator.storage.memory import MemoryStore
from investigator.storage.postgres import PostgresStore

INVESTIGATOR_DATABASE_URL = os.getenv(
    "INVESTIGATOR_DATABASE_URL",
    "postgresql://investigator:investigator@localhost:5433/investigator",
)
USE_MEMORY_STORE = os.getenv("INVESTIGATOR_USE_MEMORY", "").lower() in {"1", "true", "yes"}


def create_store():
    if USE_MEMORY_STORE:
        return MemoryStore()
    return PostgresStore(INVESTIGATOR_DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = create_store()
    try:
        store.run_migrations()
        store.seed_dependencies()
    except Exception as exc:
        if not USE_MEMORY_STORE:
            raise RuntimeError(f"failed to initialize store: {exc}") from exc
    app.state.store = store
    yield


app = FastAPI(title="Agentic SRE Investigator", version="0.1.0", lifespan=lifespan)


class IncidentResponse(BaseModel):
    incident: Incident


class EvidenceResponse(BaseModel):
    evidence: list[Evidence]


class TimelineResponse(BaseModel):
    timeline: list[TimelineEvent]


class HypothesesResponse(BaseModel):
    hypotheses: list[Hypothesis]


class ReportResponse(BaseModel):
    report: Report


@app.post("/api/v1/alerts", response_model=IncidentResponse)
def ingest_alert(payload: AlertIngest) -> IncidentResponse:
    store = app.state.store
    try:
        incident = store.ingest_alert(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IncidentResponse(incident=incident)


@app.post("/api/v1/incidents/{incident_id}/investigate", response_model=IncidentResponse)
async def investigate(incident_id: str) -> IncidentResponse:
    store = app.state.store
    try:
        incident = await run_investigation(store, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IncidentResponse(incident=incident)


@app.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str) -> IncidentResponse:
    store = app.state.store
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"incident not found: {incident_id}")
    return IncidentResponse(incident=incident)


@app.get("/api/v1/incidents/{incident_id}/evidence", response_model=EvidenceResponse)
def get_evidence(incident_id: str) -> EvidenceResponse:
    store = app.state.store
    investigation = store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"incident not found: {incident_id}")
    return EvidenceResponse(evidence=store.list_evidence(investigation.investigation_id))


@app.get("/api/v1/incidents/{incident_id}/timeline", response_model=TimelineResponse)
def get_timeline(incident_id: str) -> TimelineResponse:
    store = app.state.store
    investigation = store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"incident not found: {incident_id}")
    return TimelineResponse(timeline=store.list_timeline(investigation.investigation_id))


@app.get("/api/v1/incidents/{incident_id}/hypotheses", response_model=HypothesesResponse)
def get_hypotheses(incident_id: str) -> HypothesesResponse:
    store = app.state.store
    investigation = store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"incident not found: {incident_id}")
    return HypothesesResponse(hypotheses=store.list_hypotheses(investigation.investigation_id))


@app.get("/api/v1/incidents/{incident_id}/report", response_model=ReportResponse)
def get_report(incident_id: str) -> ReportResponse:
    store = app.state.store
    report = store.get_report_for_incident(incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"report not found for incident: {incident_id}")
    return ReportResponse(report=report)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "investigator.api.app:app",
        host=os.getenv("INVESTIGATOR_HOST", "0.0.0.0"),
        port=int(os.getenv("INVESTIGATOR_PORT", "8080")),
        reload=False,
    )


if __name__ == "__main__":
    main()

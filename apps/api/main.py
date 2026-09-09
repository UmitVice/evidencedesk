import logging
import time
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from evidencedesk.actions import apply_approved_note, ticket_history
from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError, missing
from evidencedesk.models import AnalyzeRequest, DecisionRequest
from evidencedesk.responses import (
    DecisionResponse,
    RunResponse,
    SessionResponse,
    SourceResponse,
    TicketResponse,
    TicketsResponse,
)
from evidencedesk.sessions import create_session, get_ticket, require_service, session
from evidencedesk.workflow import analyze, read_run

app = FastAPI(title="EvidenceDesk API", version="0.1.0")
Owner = Annotated[dict[str, Any], Depends(session)]
logger = logging.getLogger("evidencedesk")


@app.middleware("http")
async def boundary(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = time.monotonic()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4096:
            return JSONResponse(
                {
                    "error": {
                        "code": "body_too_large",
                        "message": "Request too large.",
                        "request_id": request.state.request_id,
                    }
                },
                status_code=413,
            )
    request._body = bytes(body)
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            {
                "error": {
                    "code": "internal_error",
                    "message": "Request failed safely.",
                    "request_id": request.state.request_id,
                }
            },
            status_code=500,
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        "request_id=%s status=%s elapsed_ms=%s",
        request.state.request_id,
        response.status_code,
        round((time.monotonic() - start) * 1000),
    )
    return response


@app.exception_handler(DomainError)
async def domain_error(request: Request, error: DomainError):
    return JSONResponse(
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "request_id": request.state.request_id,
            }
        },
        status_code=error.status,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _: RequestValidationError):
    return JSONResponse(
        {
            "error": {
                "code": "invalid_request",
                "message": "Invalid request fields.",
                "request_id": request.state.request_id,
            }
        },
        status_code=422,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidencedesk-api", "mode": settings().ai_mode}


@app.post("/sessions", dependencies=[Depends(require_service)], response_model=SessionResponse)
def start_session() -> dict[str, Any]:
    return create_session()


@app.get("/tickets", response_model=TicketsResponse)
def tickets(owner: Owner) -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id,sample,title,body,version FROM evidence.tickets "
            "WHERE session_id=%s AND tenant=%s ORDER BY sample",
            (owner["id"], owner["tenant"]),
        ).fetchall()
    return {"tickets": rows, "mode": settings().ai_mode}


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def ticket(ticket_id: UUID, owner: Owner) -> dict[str, Any]:
    return {**get_ticket(owner, str(ticket_id)), **ticket_history(owner, str(ticket_id))}


@app.get("/sources/{source_id}", response_model=SourceResponse)
def source(source_id: UUID, owner: Owner) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT c.id,c.heading,c.body,d.title,d.source_id,d.version,d.status "
            "FROM evidence.chunks c JOIN evidence.documents d ON d.id=c.document_id "
            "WHERE c.id=%s AND c.tenant=%s AND d.status='active'",
            (source_id, owner["tenant"]),
        ).fetchone()
    if not row:
        raise missing()
    return row


@app.post("/tickets/{ticket_id}/analyze", response_model=RunResponse)
def analyze_ticket(ticket_id: UUID, body: AnalyzeRequest, owner: Owner) -> dict[str, Any]:
    return analyze(owner, str(ticket_id), body.question)


@app.get("/runs/{run_id}", response_model=RunResponse)
def run(run_id: UUID, owner: Owner) -> dict[str, Any]:
    return read_run(owner, str(run_id))


@app.post("/proposals/{proposal_id}/decision", response_model=DecisionResponse)
def decide(proposal_id: UUID, body: DecisionRequest, owner: Owner) -> dict[str, Any]:
    return apply_approved_note(owner, str(proposal_id), body.decision)

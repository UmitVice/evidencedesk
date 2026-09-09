from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from evidencedesk.models import Answer


class SessionResponse(BaseModel):
    token: str
    expires_at: datetime
    mode: Literal["simulated", "live"]


class TicketSummary(BaseModel):
    id: UUID
    sample: str
    title: str
    body: str
    version: int


class TicketsResponse(BaseModel):
    tickets: list[TicketSummary]
    mode: Literal["simulated", "live"]


class NoteResponse(BaseModel):
    id: UUID
    content: str
    created_at: datetime


class AuditResponse(BaseModel):
    event: str
    proposal_id: UUID
    created_at: datetime


class RunSummary(BaseModel):
    id: UUID
    status: str
    mode: str
    created_at: datetime


class TicketResponse(TicketSummary):
    notes: list[NoteResponse]
    audit: list[AuditResponse]
    runs: list[RunSummary]


class ProposalResponse(BaseModel):
    id: UUID
    content: str
    content_hash: str
    status: Literal["pending", "applied", "rejected"]
    expires_at: datetime
    expected_version: int


class SourceResponse(BaseModel):
    id: UUID
    heading: str
    body: str
    title: str
    source_id: str
    version: int
    status: str = "active"


class RunResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    ticket_version: int
    status: Literal["running", "complete", "failed"]
    mode: Literal["simulated", "live"]
    result: Answer | None
    proposal: ProposalResponse | None
    evidence: list[SourceResponse]
    trace: dict[str, Any]
    error_code: str | None
    created_at: datetime


class DecisionResponse(BaseModel):
    status: Literal["applied", "rejected"]
    note_id: str | None
    replayed: bool

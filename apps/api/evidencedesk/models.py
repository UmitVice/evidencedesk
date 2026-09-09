from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Citation(StrictModel):
    source_id: str = Field(min_length=36, max_length=36)
    quote: str = Field(min_length=10, max_length=400)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=600)
    citations: list[Citation] = Field(min_length=1, max_length=3)


class Answer(StrictModel):
    status: Literal["answered", "insufficient_evidence"]
    claims: list[Claim] = Field(max_length=4)
    proposed_note: str | None = Field(default=None, min_length=1, max_length=1200)

    @model_validator(mode="after")
    def consistency(self):
        if self.status == "answered" and not self.claims:
            raise ValueError("Answered responses require cited claims")
        if self.status == "insufficient_evidence" and (self.claims or self.proposed_note):
            raise ValueError("Insufficient evidence cannot propose an action or factual claims")
        return self


class AnalyzeRequest(StrictModel):
    question: str = Field(default="", max_length=500)


class DecisionRequest(StrictModel):
    decision: Literal["approve", "reject"]

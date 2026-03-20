from datetime import datetime

from pydantic import BaseModel


class GenerationBase(BaseModel):
    client_name: str
    document_type: str
    case_subject: str
    facts: str
    requests: str
    legal_basis: str | None = None
    context_used: str
    generated_text: str


class GenerationCreate(GenerationBase):
    pass


class GenerationResponse(GenerationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
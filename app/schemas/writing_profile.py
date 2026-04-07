from typing import Optional

from pydantic import BaseModel, Field


class WritingProfileCreate(BaseModel):
    profile_name: str = Field(..., min_length=3, max_length=150)
    lawyer_name: Optional[str] = Field(default=None, max_length=150)
    office_name: Optional[str] = Field(default=None, max_length=200)

    tone: str = Field(default="Formal", min_length=3, max_length=100)
    qualification_style: Optional[str] = None
    opening_phrase: Optional[str] = None
    closing_phrase: Optional[str] = None
    request_intro: Optional[str] = None
    legal_style_notes: Optional[str] = None
    recurring_expressions: Optional[str] = None

    tags: Optional[str] = None
    is_favorite: bool = False
    status: Optional[str] = Field(default=None, max_length=100)

    is_active: bool = False


class WritingProfileRead(WritingProfileCreate):
    id: int

    class Config:
        from_attributes = True
from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    original_filename: str
    saved_filename: str
    file_path: str
    file_type: str
    extracted_text: str
    tags: str | None = None
    is_favorite: bool = False
    status: str | None = None


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
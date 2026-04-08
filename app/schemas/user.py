from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=150)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    full_name: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True

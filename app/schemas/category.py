from uuid import UUID

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None

    model_config = {"from_attributes": True}

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.core.security import require_roles
from app.database.connection import get_db
from app.database.models import (
    Batch,
    Faculty,
    FacultyBatch,
    Role,
    User,
)
from app.schemas.faculty import FacultyBatchAssignmentIn


router = APIRouter(
    prefix="/faculty",
    tags=["Faculty"],
)


from uuid import UUID
from pydantic import BaseModel, ConfigDict


class FacultyOut(BaseModel):
    user_id: UUID
    employee_id: str
    name: str
    email: str
    department_id: UUID | None = None

    assignedBatchIds: list[UUID] = []

    model_config = ConfigDict(from_attributes=True)


class AssignedBatchOut(BaseModel):
    id: uuid.UUID
    name: str
    department_id: uuid.UUID
    year: int
    section: str


def faculty_to_response(faculty: Faculty) -> FacultyOut:
    return FacultyOut(
        id=faculty.user_id,
        name=faculty.name,
        email=faculty.user.email,
        employee_id=faculty.employee_id,
        department_id=faculty.department_id,
        assignedBatchIds=[
            link.batch_id
            for link in faculty.batch_links
        ],
    )
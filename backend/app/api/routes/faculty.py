from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.database.connection import get_db
from app.database.models import (
    Batch,
    Faculty,
    FacultyBatch,
    Role,
    User,
)
from app.core.security import require_roles


router = APIRouter(
    prefix="/faculty",
    tags=["Faculty"],
)


# ============================================================
# SCHEMAS
# ============================================================

class FacultyOut(BaseModel):
    """
    Faculty information returned to frontend.
    """

    id: uuid.UUID
    name: str
    email: str
    employee_id: str
    department_id: uuid.UUID | None = None

    # IDs of currently assigned batches
    assignedBatchIds: list[uuid.UUID] = Field(
        default_factory=list
    )


class AssignBatchesRequest(BaseModel):
    """
    Request body for assigning/replacing batches.

    Example:
    {
        "batch_ids": [
            "batch-uuid-1",
            "batch-uuid-2"
        ]
    }
    """

    batch_ids: list[uuid.UUID] = Field(
        default_factory=list
    )


class AssignedBatchOut(BaseModel):
    """
    Detailed information about an assigned batch.
    """

    id: uuid.UUID
    name: str
    department_id: uuid.UUID
    year: int
    section: str


# ============================================================
# HELPER
# ============================================================

def faculty_to_response(
    faculty: Faculty,
) -> FacultyOut:
    """
    Convert Faculty SQLAlchemy object into API response.

    Faculty.user_id is the primary key of the faculty table
    and references users.id.
    """

    return FacultyOut(
        id=faculty.user_id,
        name=faculty.name,
        email=faculty.user.email,
        employee_id=faculty.employee_id,
        department_id=faculty.department_id,

        assignedBatchIds=[
            link.batch_id
            for link in faculty.batch_links
            if link.is_active
        ],
    )


# ============================================================
# GET FACULTY OR 404
# ============================================================

def get_faculty_or_404(
    db: Session,
    faculty_id: uuid.UUID,
    load_batches: bool = False,
) -> Faculty:
    """
    Find faculty using Faculty.user_id.
    """

    query = (
        db.query(Faculty)
        .options(
            selectinload(Faculty.user),
        )
    )

    if load_batches:
        query = query.options(
            selectinload(Faculty.batch_links)
        )

    faculty = (
        query
        .filter(
            Faculty.user_id == faculty_id
        )
        .first()
    )

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty not found",
        )

    return faculty


# ============================================================
# GET ALL FACULTY
# ============================================================

@router.get(
    "",
    response_model=list[FacultyOut],
)
def get_faculty_list(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Return all registered faculty members.

    Each faculty member contains assignedBatchIds.
    """

    faculty_members = (
        db.query(Faculty)
        .options(
            selectinload(Faculty.user),
            selectinload(Faculty.batch_links),
        )
        .order_by(
            Faculty.name.asc()
        )
        .all()
    )

    return [
        faculty_to_response(faculty)
        for faculty in faculty_members
    ]


# ============================================================
# GET ONE FACULTY
# ============================================================

@router.get(
    "/{faculty_id}",
    response_model=FacultyOut,
)
def get_faculty(
    faculty_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Return one faculty member with assigned batch IDs.
    """

    faculty = get_faculty_or_404(
        db=db,
        faculty_id=faculty_id,
        load_batches=True,
    )

    return faculty_to_response(faculty)


# ============================================================
# GET ASSIGNED BATCHES
# ============================================================

@router.get(
    "/{faculty_id}/batches",
    response_model=list[AssignedBatchOut],
)
def get_faculty_batches(
    faculty_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Return all active batches assigned to the faculty member.
    """

    # --------------------------------------------------------
    # 1. MAKE SURE FACULTY EXISTS
    # --------------------------------------------------------

    get_faculty_or_404(
        db=db,
        faculty_id=faculty_id,
        load_batches=False,
    )

    # --------------------------------------------------------
    # 2. GET ACTIVE ASSIGNMENTS
    # --------------------------------------------------------

    batches = (
        db.query(Batch)
        .join(
            FacultyBatch,
            FacultyBatch.batch_id == Batch.id,
        )
        .filter(
            FacultyBatch.faculty_id == faculty_id,
            FacultyBatch.is_active == True,
        )
        .order_by(
            Batch.name.asc()
        )
        .all()
    )

    # --------------------------------------------------------
    # 3. RETURN RESPONSE
    # --------------------------------------------------------

    return [
        AssignedBatchOut(
            id=batch.id,
            name=batch.name,
            department_id=batch.department_id,
            year=batch.year,
            section=batch.section,
        )
        for batch in batches
    ]


# ============================================================
# ASSIGN / REPLACE FACULTY BATCHES
# ============================================================

@router.put(
    "/{faculty_id}/batches",
    response_model=FacultyOut,
)
def assign_faculty_batches(
    faculty_id: uuid.UUID,
    payload: AssignBatchesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Replace the complete batch assignment of a faculty member.

    Example:

    {
        "batch_ids": [
            "uuid-1",
            "uuid-2"
        ]
    }

    If batch_ids is [] then all assignments are removed.
    """

    # ========================================================
    # 1. FIND FACULTY
    # ========================================================

    get_faculty_or_404(
        db=db,
        faculty_id=faculty_id,
        load_batches=True,
    )

    # ========================================================
    # 2. REMOVE DUPLICATE BATCH IDS
    # ========================================================

    batch_ids = list(
        dict.fromkeys(
            payload.batch_ids
        )
    )

    # ========================================================
    # 3. VALIDATE BATCHES
    # ========================================================

    batches: list[Batch] = []

    if batch_ids:

        batches = (
            db.query(Batch)
            .filter(
                Batch.id.in_(batch_ids)
            )
            .all()
        )

    found_batch_ids = {
        batch.id
        for batch in batches
    }

    missing_batch_ids = [
        batch_id
        for batch_id in batch_ids
        if batch_id not in found_batch_ids
    ]

    if missing_batch_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": (
                    "One or more batches "
                    "were not found"
                ),
                "missing_batch_ids": [
                    str(batch_id)
                    for batch_id in missing_batch_ids
                ],
            },
        )

    # ========================================================
    # 4. GET EXISTING ASSIGNMENTS
    # ========================================================

    existing_links = (
        db.query(FacultyBatch)
        .filter(
            FacultyBatch.faculty_id == faculty_id
        )
        .all()
    )

    # ========================================================
    # 5. DELETE OLD + CREATE NEW ASSIGNMENTS
    # ========================================================

    try:

        # ----------------------------------------------------
        # DELETE OLD ASSIGNMENTS
        # ----------------------------------------------------

        for link in existing_links:
            db.delete(link)

        # Make sure DELETE executes before INSERT.
        db.flush()

        # ----------------------------------------------------
        # CREATE NEW ASSIGNMENTS
        # ----------------------------------------------------

        for batch_id in batch_ids:

            assignment = FacultyBatch(
                faculty_id=faculty_id,
                batch_id=batch_id,

                # IMPORTANT FIX
                # PostgreSQL faculty_batches.is_active
                # is NOT NULL.
                is_active=True,
            )

            db.add(assignment)

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

    except Exception as exc:

        db.rollback()

        print(
            "========== FACULTY BATCH ASSIGNMENT ERROR =========="
        )
        print(
            repr(exc)
        )
        print(
            "====================================================="
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to save faculty batch assignments: "
                f"{str(exc)}"
            ),
        )

    # ========================================================
    # 6. RELOAD FACULTY
    # ========================================================

    faculty = (
        db.query(Faculty)
        .options(
            selectinload(Faculty.user),
            selectinload(Faculty.batch_links),
        )
        .filter(
            Faculty.user_id == faculty_id
        )
        .first()
    )

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Faculty not found "
                "after assignment"
            ),
        )

    # ========================================================
    # 7. RETURN UPDATED FACULTY
    # ========================================================

    return faculty_to_response(faculty)


# ============================================================
# ADD ONE BATCH
# ============================================================

@router.post(
    "/{faculty_id}/batches/{batch_id}",
    response_model=FacultyOut,
)
def add_faculty_batch(
    faculty_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Add one batch to a faculty member.

    If already assigned, nothing is changed.
    """

    # ========================================================
    # 1. FIND FACULTY
    # ========================================================

    get_faculty_or_404(
        db=db,
        faculty_id=faculty_id,
        load_batches=False,
    )

    # ========================================================
    # 2. FIND BATCH
    # ========================================================

    batch = (
        db.query(Batch)
        .filter(
            Batch.id == batch_id
        )
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # ========================================================
    # 3. CHECK EXISTING ASSIGNMENT
    # ========================================================

    existing = (
        db.query(FacultyBatch)
        .filter(
            FacultyBatch.faculty_id == faculty_id,
            FacultyBatch.batch_id == batch_id,
        )
        .first()
    )

    # ========================================================
    # 4. CREATE OR REACTIVATE ASSIGNMENT
    # ========================================================

    if existing is None:

        # ----------------------------------------------------
        # NEW ASSIGNMENT
        # ----------------------------------------------------

        db.add(
            FacultyBatch(
                faculty_id=faculty_id,
                batch_id=batch_id,

                # IMPORTANT FIX
                is_active=True,
            )
        )

    else:

        # ----------------------------------------------------
        # EXISTING ASSIGNMENT
        # ----------------------------------------------------

        # If the row already exists but was inactive,
        # reactivate it.
        existing.is_active = True

    # ========================================================
    # 5. SAVE
    # ========================================================

    try:

        db.commit()

    except Exception as exc:

        db.rollback()

        print(
            "========== ADD FACULTY BATCH ERROR =========="
        )
        print(
            repr(exc)
        )
        print(
            "=============================================="
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to assign batch: "
                f"{str(exc)}"
            ),
        )

    # ========================================================
    # 6. RELOAD FACULTY
    # ========================================================

    faculty = (
        db.query(Faculty)
        .options(
            selectinload(Faculty.user),
            selectinload(Faculty.batch_links),
        )
        .filter(
            Faculty.user_id == faculty_id
        )
        .first()
    )

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty not found",
        )

    # ========================================================
    # 7. RETURN
    # ========================================================

    return faculty_to_response(faculty)


# ============================================================
# REMOVE ONE BATCH
# ============================================================

@router.delete(
    "/{faculty_id}/batches/{batch_id}",
    response_model=FacultyOut,
)
def remove_faculty_batch(
    faculty_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMIN)
    ),
):
    """
    Remove one batch from a faculty member.
    """

    # ========================================================
    # 1. CHECK FACULTY
    # ========================================================

    get_faculty_or_404(
        db=db,
        faculty_id=faculty_id,
        load_batches=False,
    )

    # ========================================================
    # 2. FIND ACTIVE ASSIGNMENT
    # ========================================================

    assignment = (
        db.query(FacultyBatch)
        .filter(
            FacultyBatch.faculty_id == faculty_id,
            FacultyBatch.batch_id == batch_id,
            FacultyBatch.is_active == True,
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Batch is not assigned to "
                "this faculty member"
            ),
        )

    # ========================================================
    # 3. DELETE ASSIGNMENT
    # ========================================================

    db.delete(assignment)

    # ========================================================
    # 4. SAVE
    # ========================================================

    try:

        db.commit()

    except Exception as exc:

        db.rollback()

        print(
            "========== REMOVE FACULTY BATCH ERROR =========="
        )
        print(
            repr(exc)
        )
        print(
            "================================================="
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to remove batch assignment: "
                f"{str(exc)}"
            ),
        )

    # ========================================================
    # 5. RELOAD FACULTY
    # ========================================================

    faculty = (
        db.query(Faculty)
        .options(
            selectinload(Faculty.user),
            selectinload(Faculty.batch_links),
        )
        .filter(
            Faculty.user_id == faculty_id
        )
        .first()
    )

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty not found",
        )

    # ========================================================
    # 6. RETURN
    # ========================================================

    return faculty_to_response(faculty)
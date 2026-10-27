
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import Role, Student, User
from app.schemas.schemas import StudentRecordOut
from app.services import academic_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentRecordOut)
def my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
):
    """
    Return the authenticated student's dashboard profile.

    The student ID is obtained from the authenticated user,
    not from a client-supplied ID.
    """
    student = db.get(Student, user.id)

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

    active_enrollment = next(
        (
            enrollment
            for enrollment in student.enrollments
            if enrollment.enrollment_status.value == "ACTIVE"
        ),
        None,
    )

    face_enrollment = student.face_enrollment

    student_phone = next(
        (
            contact.mobile_number
            for contact in student.contacts
            if contact.contact_type.value == "STUDENT"
        ),
        "",
    )

    return {
        "id": str(student.user_id),
        "name": student.full_name,
        "rollNumber": student.roll_number,
        "department": (
            active_enrollment.batch.department.name
            if active_enrollment
            else ""
        ),
        "batchId": (
            str(active_enrollment.batch_id)
            if active_enrollment
            else ""
        ),
        "section": (
            active_enrollment.batch.section
            if active_enrollment
            else ""
        ),
        "email": user.email,
        "phone": student_phone,
        "faceEnrolled": bool(
            face_enrollment
            and face_enrollment.status.value == "COMPLETE"
        ),
        "overallAttendancePct": (
            academic_service.overall_attendance_pct(
                db,
                student.user_id,
            )
        ),
    }
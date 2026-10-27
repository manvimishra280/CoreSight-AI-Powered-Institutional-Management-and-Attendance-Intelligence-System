
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.database.models import Faculty, Role, Student, User
from app.services.audit import log_action


def resolve_user_out(user: User) -> dict:
    """Build the user response expected by the frontend."""

    base = {
        "id": str(user.id),
        "email": user.email,
        "role": user.role.value.lower(),
    }

    if user.role == Role.STUDENT and user.student_profile:
        student = user.student_profile

        batch_id = None
        active_enrollment = next(
            (
                enrollment
                for enrollment in student.enrollments
                if enrollment.enrollment_status.value == "ACTIVE"
            ),
            None,
        )

        if active_enrollment:
            batch_id = str(active_enrollment.batch_id)

        return {
            **base,
            "name": student.full_name,
            "rollNumber": student.roll_number,
            "batchId": batch_id,
        }

    if user.role == Role.FACULTY and user.faculty_profile:
        return {
            **base,
            "name": user.faculty_profile.name,
        }

    if user.role == Role.ADMIN and user.admin_profile:
        return {
            **base,
            "name": user.admin_profile.name,
        }

    return {
        **base,
        "name": user.email,
    }


def authenticate(
    db: Session,
    email: str,
    password: str,
) -> tuple[User, str] | None:
    """Authenticate an active account and issue a JWT."""

    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    from app.database.base import utcnow

    user.last_login_at = utcnow()

    try:
        db.commit()

        token = create_access_token(
            user.id,
            user.role.value,
        )

        log_action(
            db,
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="user",
            entity_id=str(user.id),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return user, token

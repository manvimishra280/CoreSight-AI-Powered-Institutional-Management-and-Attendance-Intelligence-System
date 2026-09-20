"""
Registration sync: Google Form response -> normalized CoreSight records.

Two entry points:
- sync_submission() - the core, transactional normalizer. Called directly
  by the manual/per-response endpoint, and by
  registration_sync_orchestrator.py for each response fetched live from
  Google.
- Retry semantics: a submission in a terminal state (SYNCED, REJECTED,
  DUPLICATE) is returned unchanged - it is never reprocessed. A submission
  in a non-terminal state (PENDING, PROCESSING, FAILED - i.e. it was
  interrupted or hit a transient error) is reprocessed in place on retry,
  never duplicated, because google_response_id is UNIQUE and looked up
  first.
"""

import re
import uuid
import logging
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.models import (
    ContactType,
    EnrollmentStatus,
    QualificationType,
    RegistrationForm,
    RegistrationSubmission,
    Role,
    Student,
    StudentAddress,
    StudentContact,
    StudentEnrollment,
    StudentQualification,
    SubmissionStatus,
    User,
)
from app.services.audit import log_action

_PLACEHOLDER_PASSWORD_PREFIX = "unset:"  # student sets a real password via the activation flow - see activation_service.py

_TERMINAL_STATUSES = {SubmissionStatus.SYNCED, SubmissionStatus.REJECTED, SubmissionStatus.DUPLICATE}


def _temp_password_hash() -> str:
    # Never a usable password - the account stays inactive
    # (users.is_active=False) until activation_service.activate_account()
    # sets a real one. See registration_forms field_mapping doc / README
    # "Student account activation".
    return hash_password(f"{_PLACEHOLDER_PASSWORD_PREFIX}{uuid.uuid4()}")


def sync_submission(
    db: Session, form: RegistrationForm, google_response_id: str, submitted_at: datetime, raw: dict
) -> RegistrationSubmission:
    """
    Idempotent and retry-safe. Returns the RegistrationSubmission row
    (inspect `.status` for the outcome - PROCESSING here should never be
    visible to a caller since this function resolves synchronously to a
    terminal-for-this-attempt status before returning).
    """
    existing = db.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == google_response_id).first()
    if existing and existing.status in _TERMINAL_STATUSES:
        return existing

    submission = existing or RegistrationSubmission(
        form_id=form.id,
        google_response_id=google_response_id,
        submitted_at=submitted_at,
        raw_response=raw,
        status=SubmissionStatus.PENDING,
    )
    if existing is None:
        db.add(submission)
    submission.status = SubmissionStatus.PROCESSING
    submission.error_message = None
    db.flush()

    try:
        roll_number = raw["roll_number"].strip()
        email = raw["email"].strip().lower()
        full_name = raw["name"].strip()

        # --- explicit conflict handling (spec: do not silently overwrite) ---
        conflicting_user = db.query(User).filter(User.email == email).first()
        conflicting_student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if conflicting_student and conflicting_student.user.email != email:
            submission.status = SubmissionStatus.DUPLICATE
            submission.error_message = f"Roll number {roll_number} is already registered to a different email."
            db.commit()
            log_action(db, user_id=None, action="REGISTRATION_DUPLICATE", entity_type="registration_submission", entity_id=str(submission.id),
                       metadata={"reason": "roll_number_conflict", "google_response_id": google_response_id})
            db.commit()
            return submission
        if conflicting_user and conflicting_user.role != Role.STUDENT:
            submission.status = SubmissionStatus.DUPLICATE
            submission.error_message = f"Email {email} is already registered to a non-student account."
            db.commit()
            log_action(db, user_id=None, action="REGISTRATION_DUPLICATE", entity_type="registration_submission", entity_id=str(submission.id),
                       metadata={"reason": "email_role_conflict", "google_response_id": google_response_id})
            db.commit()
            return submission

        user = conflicting_user
        if user is None:
            user = User(email=email, password_hash=_temp_password_hash(), role=Role.STUDENT, is_active=False)
            db.add(user)
            db.flush()

        student = db.get(Student, user.id)
        if student is None:
            student = Student(
                user_id=user.id,
                roll_number=roll_number,
                full_name=full_name,
                gender=raw.get("gender"),
                date_of_birth=_parse_iso_date(raw.get("date_of_birth")),
            )
            db.add(student)
            db.flush()
        elif student.roll_number != roll_number:
            # Same email, different roll number on retry/resubmit - treat as
            # a conflict rather than silently changing an existing student's
            # identity.
            submission.status = SubmissionStatus.DUPLICATE
            submission.error_message = f"Email {email} is already registered under roll number {student.roll_number}."
            db.commit()
            log_action(db, user_id=None, action="REGISTRATION_DUPLICATE", entity_type="registration_submission", entity_id=str(submission.id),
                       metadata={"reason": "email_roll_number_mismatch", "google_response_id": google_response_id})
            db.commit()
            return submission

        existing_enrollment = db.query(StudentEnrollment).filter(
            StudentEnrollment.student_id == student.user_id, StudentEnrollment.batch_id == form.batch_id
        ).first()
        if existing_enrollment is None:
            db.add(StudentEnrollment(
                student_id=student.user_id,
                batch_id=form.batch_id,
                semester=raw.get("semester"),
                enrollment_status=EnrollmentStatus.ACTIVE,
            ))

        _upsert_contact(db, student.user_id, ContactType.STUDENT, full_name, raw.get("student_mobile"), is_primary=True)
        if raw.get("father_name") or raw.get("father_mobile"):
            _upsert_contact(db, student.user_id, ContactType.FATHER, raw.get("father_name", ""), raw.get("father_mobile"))
        if raw.get("mother_name") or raw.get("mother_mobile"):
            _upsert_contact(db, student.user_id, ContactType.MOTHER, raw.get("mother_name", ""), raw.get("mother_mobile"))
        if raw.get("guardian_mobile") and not (raw.get("father_mobile") or raw.get("mother_mobile")):
            _upsert_contact(db, student.user_id, ContactType.GUARDIAN, raw.get("guardian_name", ""), raw.get("guardian_mobile"))

        if raw.get("address"):
            addr = db.query(StudentAddress).filter(StudentAddress.student_id == student.user_id).first()
            if addr is None:
                db.add(StudentAddress(student_id=student.user_id, address_line=raw["address"]))

        for qtype, prefix in (
            (QualificationType.HIGH_SCHOOL, "high_school"),
            (QualificationType.INTERMEDIATE, "intermediate"),
            (QualificationType.DIPLOMA, "diploma"),
        ):
            board = raw.get(f"{prefix}_board")
            if not board:
                continue  # e.g. no diploma - simply no row, per spec
            existing_q = db.query(StudentQualification).filter(
                StudentQualification.student_id == student.user_id, StudentQualification.qualification_type == qtype
            ).first()
            if existing_q is None:
                db.add(StudentQualification(
                    student_id=student.user_id,
                    qualification_type=qtype,
                    board=board,
                    institution=raw.get(f"{prefix}_institution"),
                    passing_year=raw.get(f"{prefix}_passing_year"),
                    score=raw.get(f"{prefix}_score"),
                    score_type=raw.get(f"{prefix}_score_type"),
                    roll_number=raw.get(f"{prefix}_roll_number"),
                ))

        submission.student_id = student.user_id
        submission.status = SubmissionStatus.SYNCED
        submission.synced_at = datetime.now(submitted_at.tzinfo)
        submission.error_message = None

        log_action(db, user_id=None, action="STUDENT_ACCOUNT_CREATED", entity_type="student", entity_id=str(student.user_id),
                   metadata={"google_response_id": google_response_id, "registration_submission_id": str(submission.id)})
        log_action(db, user_id=None, action="REGISTRATION_SYNCED", entity_type="registration_submission", entity_id=str(submission.id),
                   metadata={"batch_id": str(form.batch_id), "student_id": str(student.user_id)})
        db.commit()

        if raw.get("profile_photo_file_id"):
            _attach_profile_photo(db, student, raw["profile_photo_file_id"])

        _issue_activation(db, user)
        return submission

    except KeyError as e:
        db.rollback()
        submission = db.get(RegistrationSubmission, submission.id) or submission
        submission.status = SubmissionStatus.REJECTED
        submission.error_message = f"Missing required field in submission: {e}"
        db.add(submission)
        log_action(db, user_id=None, action="REGISTRATION_REJECTED", entity_type="registration_submission", entity_id=str(submission.id),
                   metadata={"reason": str(e), "google_response_id": google_response_id})
        db.commit()
        return submission

    except IntegrityError as e:
        db.rollback()
        submission = db.get(RegistrationSubmission, submission.id) or submission
        submission.status = SubmissionStatus.FAILED
        submission.error_message = "A database conflict occurred while creating this student. Safe to retry."
        db.add(submission)
        log_action(db, user_id=None, action="REGISTRATION_SYNC_FAILED", entity_type="registration_submission", entity_id=str(submission.id),
                   metadata={"reason": "integrity_error", "google_response_id": google_response_id})
        db.commit()
        return submission


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _issue_activation(db: Session, user: User) -> None:
    """
    Best-effort: a new student account always gets an activation token
    (real, hashed, single-use - see activation_service.py), but email
    delivery isn't wired up in this environment (send_activation_email is a
    documented stub). Failing to deliver the email must never fail the
    registration itself - the token still exists and an admin can look the
    student up and re-trigger activation through a real email provider once
    one is configured.
    """
    from app.services import activation_service

    if not user.is_active:
        raw_token = activation_service.create_activation_token(db, user)
        db.commit()
        try:
            activation_service.send_activation_email(user, raw_token)
        except NotImplementedError:
            pass


def _attach_profile_photo(db: Session, student: Student, drive_file_id: str) -> None:
    """
    Best-effort, non-blocking: a profile-photo failure (Drive/Storage not
    configured, unsupported file type, etc.) must never fail registration
    itself. See storage_service.py.
    """
    from app.services.storage_service import ProfilePhotoError, upload_profile_photo_from_drive

    try:
        path = upload_profile_photo_from_drive(drive_file_id, student.user_id)
        student.profile_photo_path = path
        db.commit()
    except ProfilePhotoError as e:
        logging.getLogger("coresight.registration_sync").warning(
            "PROFILE_PHOTO_SKIPPED student_id=%s reason=%s", student.user_id, e
        )


def _upsert_contact(db: Session, student_id: uuid.UUID, contact_type: ContactType, name: str, mobile: str | None, is_primary: bool = False) -> None:
    if not mobile:
        return
    existing = db.query(StudentContact).filter(
        StudentContact.student_id == student_id, StudentContact.contact_type == contact_type
    ).first()
    if existing:
        return
    db.add(StudentContact(
        student_id=student_id, contact_type=contact_type, name=name or contact_type.value.title(),
        mobile_number=mobile, is_primary=is_primary,
    ))

"""
Registration sync: Google Form response -> normalized CoreSight records.

Two entry points:
- sync_submission() - the core, transactional normalizer. Called directly
  by the manual/per-response endpoint, and by
  registration_sync_orchestrator.py for each response fetched live from
  Google.

Retry semantics:
- A submission in a terminal state (SYNCED, REJECTED, DUPLICATE) is returned
  unchanged - it is never reprocessed.
- A submission in a non-terminal state (PENDING, PROCESSING, FAILED) is
  reprocessed in place on retry.
- google_response_id is unique, so a Google response can never create a
  second RegistrationSubmission row.

Student account workflow:
- A new student receives a real temporary password.
- The password is stored only as a hash in the database.
- The student account is active immediately.
- must_change_password=True forces the student to change the temporary
  password after the first successful login.
- The temporary password is sent to the student's email address.
- No activation token is required for the student registration workflow.
"""

from __future__ import annotations

import logging
import uuid
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
from app.services.credential_service import generate_temporary_password
from app.services.email_service import send_student_credentials_email


logger = logging.getLogger("coresight.registration_sync")


_TERMINAL_STATUSES = {
    SubmissionStatus.SYNCED,
    SubmissionStatus.REJECTED,
    SubmissionStatus.DUPLICATE,
}


def sync_submission(
    db: Session,
    form: RegistrationForm,
    google_response_id: str,
    submitted_at: datetime,
    raw: dict,
) -> RegistrationSubmission:
    """
    Synchronize one Google Form response into CoreSight.

    This function is idempotent and retry-safe.

    For a new student:
        1. Validate required registration fields.
        2. Check email/roll-number conflicts.
        3. Generate a temporary password.
        4. Create an active STUDENT user with must_change_password=True.
        5. Create the Student profile.
        6. Create the StudentEnrollment for the form's batch.
        7. Create contacts/address/qualifications where supplied.
        8. Mark the registration submission SYNCED.
        9. Commit the database transaction.
       10. Send the temporary credentials email.

    The email is intentionally sent after the database commit. Therefore,
    an SMTP failure does not roll back an otherwise successful registration.

    Returns:
        RegistrationSubmission
    """

    # ------------------------------------------------------------------
    # 1. Idempotency / retry lookup
    # ------------------------------------------------------------------

    existing = (
        db.query(RegistrationSubmission)
        .filter(
            RegistrationSubmission.google_response_id
            == google_response_id
        )
        .first()
    )

    if existing and existing.status in _TERMINAL_STATUSES:
        return existing

    # ------------------------------------------------------------------
    # 2. Create or reuse submission record
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 3. Normalize and validate the Google Form response
    # ------------------------------------------------------------------

    try:
        roll_number = raw["roll_number"].strip()
        email = raw["email"].strip().lower()
        full_name = raw["name"].strip()

        if not roll_number:
            raise KeyError("roll_number")

        if not email:
            raise KeyError("email")

        if not full_name:
            raise KeyError("name")

        # --------------------------------------------------------------
        # 4. Explicit conflict handling
        #
        # Never silently overwrite an existing student's identity.
        # --------------------------------------------------------------

        conflicting_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        conflicting_student = (
            db.query(Student)
            .filter(Student.roll_number == roll_number)
            .first()
        )

        # --------------------------------------------------------------
        # Roll number already belongs to a different email
        # --------------------------------------------------------------

        if (
            conflicting_student
            and conflicting_student.user.email != email
        ):
            submission.status = SubmissionStatus.DUPLICATE
            submission.error_message = (
                f"Roll number {roll_number} is already registered "
                f"to a different email."
            )

            db.commit()

            log_action(
                db,
                user_id=None,
                action="REGISTRATION_DUPLICATE",
                entity_type="registration_submission",
                entity_id=str(submission.id),
                metadata={
                    "reason": "roll_number_conflict",
                    "google_response_id": google_response_id,
                },
            )

            db.commit()

            return submission

        # --------------------------------------------------------------
        # Email already belongs to a non-student account
        # --------------------------------------------------------------

        if (
            conflicting_user
            and conflicting_user.role != Role.STUDENT
        ):
            submission.status = SubmissionStatus.DUPLICATE
            submission.error_message = (
                f"Email {email} is already registered "
                f"to a non-student account."
            )

            db.commit()

            log_action(
                db,
                user_id=None,
                action="REGISTRATION_DUPLICATE",
                entity_type="registration_submission",
                entity_id=str(submission.id),
                metadata={
                    "reason": "email_role_conflict",
                    "google_response_id": google_response_id,
                },
            )

            db.commit()

            return submission

        # ------------------------------------------------------------------
        # 5. Create or reuse student user
        # ------------------------------------------------------------------

        user = conflicting_user
        temporary_password: str | None = None
        new_user_created = False

        if user is None:
            # ----------------------------------------------------------
            # IMPORTANT:
            # Generate a real temporary password.
            #
            # The plaintext password is kept only in memory long enough
            # to send the credentials email. Only its hash is stored.
            # ----------------------------------------------------------

            temporary_password = generate_temporary_password()

            user = User(
                email=email,
                password_hash=hash_password(
                    temporary_password
                ),
                role=Role.STUDENT,
                is_active=True,
                must_change_password=True,
            )

            db.add(user)
            db.flush()

            new_user_created = True

        else:
            # ----------------------------------------------------------
            # Existing student account.
            #
            # Do not silently replace an existing student's password.
            # The temporary password is only generated for a newly
            # created student account.
            # ----------------------------------------------------------

            if user.role != Role.STUDENT:
                submission.status = SubmissionStatus.DUPLICATE
                submission.error_message = (
                    f"Email {email} is already registered "
                    f"to a non-student account."
                )

                db.commit()

                log_action(
                    db,
                    user_id=None,
                    action="REGISTRATION_DUPLICATE",
                    entity_type="registration_submission",
                    entity_id=str(submission.id),
                    metadata={
                        "reason": "email_role_conflict",
                        "google_response_id": google_response_id,
                    },
                )

                db.commit()

                return submission

        # ------------------------------------------------------------------
        # 6. Create or validate Student profile
        # ------------------------------------------------------------------

        student = db.get(Student, user.id)

        if student is None:
            student = Student(
                user_id=user.id,
                roll_number=roll_number,
                full_name=full_name,
                gender=raw.get("gender"),
                date_of_birth=_parse_iso_date(
                    raw.get("date_of_birth")
                ),
            )

            db.add(student)
            db.flush()

        else:
            # ----------------------------------------------------------
            # Same email but a different roll number is an identity
            # conflict. Never overwrite it.
            # ----------------------------------------------------------

            if student.roll_number != roll_number:
                submission.status = SubmissionStatus.DUPLICATE
                submission.error_message = (
                    f"Email {email} is already registered under "
                    f"roll number {student.roll_number}."
                )

                db.commit()

                log_action(
                    db,
                    user_id=None,
                    action="REGISTRATION_DUPLICATE",
                    entity_type="registration_submission",
                    entity_id=str(submission.id),
                    metadata={
                        "reason": "email_roll_number_mismatch",
                        "google_response_id": google_response_id,
                    },
                )

                db.commit()

                return submission

        # ------------------------------------------------------------------
        # 7. Create batch enrollment
        #
        # The batch comes from the RegistrationForm.
        #
        # Faculty creates/owns the batch and its Google registration form.
        # This service only consumes form.batch_id.
        # ------------------------------------------------------------------

        existing_enrollment = (
            db.query(StudentEnrollment)
            .filter(
                StudentEnrollment.student_id == student.user_id,
                StudentEnrollment.batch_id == form.batch_id,
            )
            .first()
        )

        if existing_enrollment is None:
            db.add(
                StudentEnrollment(
                    student_id=student.user_id,
                    batch_id=form.batch_id,
                    semester=raw.get("semester"),
                    enrollment_status=EnrollmentStatus.ACTIVE,
                )
            )

        # ------------------------------------------------------------------
        # 8. Student contact information
        # ------------------------------------------------------------------

        _upsert_contact(
            db,
            student.user_id,
            ContactType.STUDENT,
            full_name,
            raw.get("student_mobile"),
            is_primary=True,
        )

        if raw.get("father_name") or raw.get("father_mobile"):
            _upsert_contact(
                db,
                student.user_id,
                ContactType.FATHER,
                raw.get("father_name", ""),
                raw.get("father_mobile"),
            )

        if raw.get("mother_name") or raw.get("mother_mobile"):
            _upsert_contact(
                db,
                student.user_id,
                ContactType.MOTHER,
                raw.get("mother_name", ""),
                raw.get("mother_mobile"),
            )

        if (
            raw.get("guardian_mobile")
            and not raw.get("father_mobile")
            and not raw.get("mother_mobile")
        ):
            _upsert_contact(
                db,
                student.user_id,
                ContactType.GUARDIAN,
                raw.get("guardian_name", ""),
                raw.get("guardian_mobile"),
            )

        # ------------------------------------------------------------------
        # 9. Student address
        # ------------------------------------------------------------------

        if raw.get("address"):
            addr = (
                db.query(StudentAddress)
                .filter(
                    StudentAddress.student_id
                    == student.user_id
                )
                .first()
            )

            if addr is None:
                db.add(
                    StudentAddress(
                        student_id=student.user_id,
                        address_line=raw["address"],
                    )
                )

        # ------------------------------------------------------------------
        # 10. Educational qualifications
        # ------------------------------------------------------------------

        for qtype, prefix in (
            (
                QualificationType.HIGH_SCHOOL,
                "high_school",
            ),
            (
                QualificationType.INTERMEDIATE,
                "intermediate",
            ),
            (
                QualificationType.DIPLOMA,
                "diploma",
            ),
        ):
            board = raw.get(f"{prefix}_board")

            if not board:
                continue

            existing_q = (
                db.query(StudentQualification)
                .filter(
                    StudentQualification.student_id
                    == student.user_id,
                    StudentQualification.qualification_type
                    == qtype,
                )
                .first()
            )

            if existing_q is None:
                db.add(
                    StudentQualification(
                        student_id=student.user_id,
                        qualification_type=qtype,
                        board=board,
                        institution=raw.get(
                            f"{prefix}_institution"
                        ),
                        passing_year=raw.get(
                            f"{prefix}_passing_year"
                        ),
                        score=raw.get(
                            f"{prefix}_score"
                        ),
                        score_type=raw.get(
                            f"{prefix}_score_type"
                        ),
                        roll_number=raw.get(
                            f"{prefix}_roll_number"
                        ),
                    )
                )

        # ------------------------------------------------------------------
        # 11. Mark registration as successfully synchronized
        # ------------------------------------------------------------------

        submission.student_id = student.user_id
        submission.status = SubmissionStatus.SYNCED
        submission.synced_at = datetime.now(
            submitted_at.tzinfo
        )
        submission.error_message = None

        # ------------------------------------------------------------------
        # 12. Audit logging
        # ------------------------------------------------------------------

        if new_user_created:
            log_action(
                db,
                user_id=None,
                action="STUDENT_ACCOUNT_CREATED",
                entity_type="student",
                entity_id=str(student.user_id),
                metadata={
                    "google_response_id": google_response_id,
                    "registration_submission_id": str(
                        submission.id
                    ),
                    "must_change_password": True,
                },
            )

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_SYNCED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "batch_id": str(form.batch_id),
                "student_id": str(student.user_id),
                "google_response_id": google_response_id,
            },
        )

        # ------------------------------------------------------------------
        # 13. Commit the student registration FIRST
        #
        # Email must not determine whether the database registration
        # succeeds.
        # ------------------------------------------------------------------

        db.commit()

        # ------------------------------------------------------------------
        # 14. Profile photo is best-effort
        # ------------------------------------------------------------------

        if raw.get("profile_photo_file_id"):
            _attach_profile_photo(
                db,
                student,
                raw["profile_photo_file_id"],
            )

        # ------------------------------------------------------------------
        # 15. Send temporary credentials to newly created student
        #
        # The plaintext temporary password exists only in this function
        # during the initial registration attempt.
        # ------------------------------------------------------------------

        if new_user_created and temporary_password:
            _send_student_credentials(
                email=user.email,
                full_name=student.full_name,
                temporary_password=temporary_password,
                user_id=user.id,
            )

        return submission

    # ------------------------------------------------------------------
    # Missing required registration field
    # ------------------------------------------------------------------

    except KeyError as e:
        db.rollback()

        submission = (
            db.get(
                RegistrationSubmission,
                submission.id,
            )
            or submission
        )

        submission.status = SubmissionStatus.REJECTED
        submission.error_message = (
            f"Missing required field in submission: {e}"
        )

        db.add(submission)

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_REJECTED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "reason": str(e),
                "google_response_id": google_response_id,
            },
        )

        db.commit()

        return submission

    # ------------------------------------------------------------------
    # Database integrity failure
    # ------------------------------------------------------------------

    except IntegrityError:
        db.rollback()

        submission = (
            db.get(
                RegistrationSubmission,
                submission.id,
            )
            or submission
        )

        submission.status = SubmissionStatus.FAILED
        submission.error_message = (
            "A database conflict occurred while creating this "
            "student. Safe to retry."
        )

        db.add(submission)

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_SYNC_FAILED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "reason": "integrity_error",
                "google_response_id": google_response_id,
            },
        )

        db.commit()

        return submission

    # ------------------------------------------------------------------
    # Unexpected failure
    # ------------------------------------------------------------------

    except Exception as exc:
        db.rollback()

        submission = (
            db.get(
                RegistrationSubmission,
                submission.id,
            )
            or submission
        )

        submission.status = SubmissionStatus.FAILED
        submission.error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        db.add(submission)

        logger.exception(
            "REGISTRATION_SYNC_FAILED "
            "submission_id=%s google_response_id=%s",
            submission.id,
            google_response_id,
        )

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_SYNC_FAILED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "reason": "unexpected_error",
                "google_response_id": google_response_id,
                "error_type": type(exc).__name__,
            },
        )

        db.commit()

        return submission


def _parse_iso_date(value: str | None) -> date | None:
    """
    Parse an ISO date supplied by the registration form.

    Invalid or empty dates are treated as None rather than failing the
    complete registration.
    """

    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _send_student_credentials(
    *,
    email: str,
    full_name: str,
    temporary_password: str,
    user_id: uuid.UUID,
) -> bool:
    """
    Send the student's initial login credentials.

    Database creation has already been committed before this function is
    called. Therefore an SMTP failure must not destroy the student account.

    Returns:
        True if the email was sent successfully.
        False if email delivery failed.
    """

    try:
        send_student_credentials_email(
            email=email,
            full_name=full_name,
            temporary_password=temporary_password,
        )

        logger.info(
            "STUDENT_CREDENTIAL_EMAIL_SENT user_id=%s email=%s",
            user_id,
            email,
        )

        return True

    except Exception as exc:
        logger.exception(
            "STUDENT_CREDENTIAL_EMAIL_FAILED "
            "user_id=%s email=%s error=%s",
            user_id,
            email,
            exc,
        )

        return False


def _attach_profile_photo(
    db: Session,
    student: Student,
    drive_file_id: str,
) -> None:
    """
    Best-effort, non-blocking profile-photo attachment.

    A Drive/Storage failure must never invalidate an otherwise successful
    student registration.
    """

    from app.services.storage_service import (
        ProfilePhotoError,
        upload_profile_photo_from_drive,
    )

    try:
        path = upload_profile_photo_from_drive(
            drive_file_id,
            student.user_id,
        )

        student.profile_photo_path = path

        db.commit()

    except ProfilePhotoError as e:
        logger.warning(
            "PROFILE_PHOTO_SKIPPED student_id=%s reason=%s",
            student.user_id,
            e,
        )


def _upsert_contact(
    db: Session,
    student_id: uuid.UUID,
    contact_type: ContactType,
    name: str,
    mobile: str | None,
    is_primary: bool = False,
) -> None:
    """
    Insert a contact only when a mobile number exists and the contact type
    is not already present.
    """

    if not mobile:
        return

    existing = (
        db.query(StudentContact)
        .filter(
            StudentContact.student_id == student_id,
            StudentContact.contact_type == contact_type,
        )
        .first()
    )

    if existing:
        return

    db.add(
        StudentContact(
            student_id=student_id,
            contact_type=contact_type,
            name=(
                name
                or contact_type.value.title()
            ),
            mobile_number=mobile,
            is_primary=is_primary,
        )
    )
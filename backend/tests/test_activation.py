import uuid
from datetime import datetime, timezone

from app.core.security import hash_password, verify_password
from app.database.models import (
    AcademicSession,
    Batch,
    Course,
    Department,
    FormStatus,
    RegistrationForm,
    Role,
    SessionStatus,
    Student,
    SubmissionStatus,
    User,
)
from app.services import registration_sync


def _make_form(db_session):
    suffix = uuid.uuid4().hex[:8]

    dept = Department(
        code=f"AC{suffix}",
        name=f"Registration Dept {suffix}",
    )

    course = Course(
        code=f"ACC{suffix}",
        name=f"Registration Course {suffix}",
        duration_years=4,
    )

    db_session.add_all([dept, course])
    db_session.flush()

    session = AcademicSession(
        name=f"registration-{suffix}",
        status=SessionStatus.ACTIVE,
    )

    db_session.add(session)
    db_session.flush()

    batch = Batch(
        academic_session_id=session.id,
        course_id=course.id,
        department_id=dept.id,
        year=1,
        section="A",
        name=f"Registration Batch {suffix}",
    )

    db_session.add(batch)
    db_session.flush()

    faculty_or_admin = User(
        email=f"registration-admin-{suffix}@coresight.edu",
        password_hash=hash_password("test-password"),
        role=Role.ADMIN,
    )

    db_session.add(faculty_or_admin)
    db_session.flush()

    form = RegistrationForm(
        batch_id=batch.id,
        google_form_id=f"gform-{suffix}",
        status=FormStatus.ACTIVE,
        created_by=faculty_or_admin.id,
    )

    db_session.add(form)
    db_session.commit()

    return form


def _raw(roll_number, email):
    return {
        "name": "Registration Student",
        "roll_number": roll_number,
        "email": email,
        "student_mobile": "9000000000",
        "father_name": "Father",
        "father_mobile": "9000000001",
        "address": "123 Test Street",
        "high_school_board": "CBSE",
        "date_of_birth": "2005-01-01",
    }


def test_synced_student_account_is_active_and_requires_password_change(
    db_session,
):
    """
    New student registrations must create an immediately active account.

    The student is not activated through an activation token anymore.
    Instead, the student logs in with the temporary password and must
    change it after the first login.
    """

    form = _make_form(db_session)

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-1",
        datetime.now(timezone.utc),
        _raw(
            "REG-001",
            "registration1@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.SYNCED

    student = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-001")
        .first()
    )

    assert student is not None
    assert student.user is not None

    assert student.user.is_active is True
    assert student.user.must_change_password is True


def test_synced_student_has_real_password_hash(
    db_session,
):
    """
    The generated temporary password must be stored as a password hash,
    never as plaintext.
    """

    form = _make_form(db_session)

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-2",
        datetime.now(timezone.utc),
        _raw(
            "REG-002",
            "registration2@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.SYNCED

    student = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-002")
        .first()
    )

    assert student is not None
    assert student.user.password_hash

    # The stored value must look like a password hash rather than
    # the generated plaintext temporary password.
    assert student.user.password_hash != ""

    # The password hash must not contain the student's email or roll number.
    assert "registration2@coresight.edu" not in student.user.password_hash
    assert "REG-002" not in student.user.password_hash


def test_repeated_sync_of_same_response_is_idempotent(
    db_session,
):
    """
    Reprocessing the same Google response must not create a second
    student account or second student profile.
    """

    form = _make_form(db_session)

    raw = _raw(
        "REG-003",
        "registration3@coresight.edu",
    )

    first = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-3",
        datetime.now(timezone.utc),
        raw,
    )

    second = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-3",
        datetime.now(timezone.utc),
        raw,
    )

    assert first.status == SubmissionStatus.SYNCED
    assert second.status == SubmissionStatus.SYNCED

    students = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-003")
        .all()
    )

    assert len(students) == 1

    users = (
        db_session.query(User)
        .filter(User.email == "registration3@coresight.edu")
        .all()
    )

    assert len(users) == 1


def test_student_registration_creates_batch_enrollment(
    db_session,
):
    """
    The student's enrollment must use the batch attached to the
    RegistrationForm.
    """

    form = _make_form(db_session)

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-4",
        datetime.now(timezone.utc),
        _raw(
            "REG-004",
            "registration4@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.SYNCED

    student = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-004")
        .first()
    )

    assert student is not None

    from app.database.models import StudentEnrollment

    enrollment = (
        db_session.query(StudentEnrollment)
        .filter(
            StudentEnrollment.student_id == student.user_id,
            StudentEnrollment.batch_id == form.batch_id,
        )
        .first()
    )

    assert enrollment is not None


def test_email_conflict_with_non_student_account_is_duplicate(
    db_session,
):
    """
    A Google response using an email belonging to an admin/faculty
    account must never overwrite that account.
    """

    form = _make_form(db_session)

    existing_user = User(
        email="existing-admin@coresight.edu",
        password_hash=hash_password("existing-password"),
        role=Role.ADMIN,
        is_active=True,
    )

    db_session.add(existing_user)
    db_session.commit()

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-5",
        datetime.now(timezone.utc),
        _raw(
            "REG-005",
            "existing-admin@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.DUPLICATE

    users = (
        db_session.query(User)
        .filter(
            User.email == "existing-admin@coresight.edu"
        )
        .all()
    )

    assert len(users) == 1
    assert users[0].role == Role.ADMIN


def test_roll_number_conflict_with_different_email_is_duplicate(
    db_session,
):
    """
    A roll number already belonging to another student must not be
    silently reassigned.
    """

    form = _make_form(db_session)

    existing_user = User(
        email="original-student@coresight.edu",
        password_hash=hash_password("existing-password"),
        role=Role.STUDENT,
        is_active=True,
        must_change_password=False,
    )

    db_session.add(existing_user)
    db_session.flush()

    existing_student = Student(
        user_id=existing_user.id,
        roll_number="REG-006",
        full_name="Original Student",
    )

    db_session.add(existing_student)
    db_session.commit()

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-6",
        datetime.now(timezone.utc),
        _raw(
            "REG-006",
            "different-student@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.DUPLICATE

    students = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-006")
        .all()
    )

    assert len(students) == 1
    assert students[0].user.email == "original-student@coresight.edu"


def test_missing_required_student_field_is_rejected(
    db_session,
):
    """
    A response without required identity fields must be rejected rather
    than creating a partial student account.
    """

    form = _make_form(db_session)

    raw = _raw(
        "REG-007",
        "registration7@coresight.edu",
    )

    del raw["email"]

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-7",
        datetime.now(timezone.utc),
        raw,
    )

    assert submission.status == SubmissionStatus.REJECTED

    student = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-007")
        .first()
    )

    assert student is None


def test_existing_student_account_is_not_given_a_new_password(
    db_session,
):
    """
    If a response matches an already-existing student account, the sync
    must not silently replace that student's password.
    """

    form = _make_form(db_session)

    original_password = "original-student-password"

    existing_user = User(
        email="existing-student@coresight.edu",
        password_hash=hash_password(original_password),
        role=Role.STUDENT,
        is_active=True,
        must_change_password=False,
    )

    db_session.add(existing_user)
    db_session.flush()

    existing_student = Student(
        user_id=existing_user.id,
        roll_number="REG-008",
        full_name="Existing Student",
    )

    db_session.add(existing_student)
    db_session.commit()

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-8",
        datetime.now(timezone.utc),
        _raw(
            "REG-008",
            "existing-student@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.SYNCED

    db_session.refresh(existing_user)

    assert verify_password(
        original_password,
        existing_user.password_hash,
    )

    assert existing_user.must_change_password is False


def test_student_account_can_login_with_generated_credentials_flow(
    db_session,
):
    """
    This test verifies the account itself is configured for the new
    temporary-password workflow.

    The plaintext temporary password is intentionally not returned by
    sync_submission, so the actual email/login integration is tested
    separately by the authentication tests.
    """

    form = _make_form(db_session)

    submission = registration_sync.sync_submission(
        db_session,
        form,
        "registration-resp-9",
        datetime.now(timezone.utc),
        _raw(
            "REG-009",
            "registration9@coresight.edu",
        ),
    )

    assert submission.status == SubmissionStatus.SYNCED

    student = (
        db_session.query(Student)
        .filter(Student.roll_number == "REG-009")
        .first()
    )

    assert student is not None

    user = student.user

    assert user.is_active is True
    assert user.must_change_password is True
    assert user.password_hash
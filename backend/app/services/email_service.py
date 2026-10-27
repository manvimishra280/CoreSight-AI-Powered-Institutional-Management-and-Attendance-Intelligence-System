import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings


def _send_email(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """
    Send a plain-text email using the configured SMTP server.

    Raises:
        RuntimeError: If SMTP is not configured.
        smtplib.SMTPException: If the SMTP server rejects/fails the message.
    """

    settings = get_settings()

    if not settings.smtp_configured:
        raise RuntimeError(
            "SMTP is not configured"
        )

    message = MIMEMultipart()

    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject

    message.attach(
        MIMEText(
            body,
            "plain",
            "utf-8",
        )
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=30,
    ) as server:
        server.starttls()

        server.login(
            settings.smtp_username,
            settings.smtp_password,
        )

        server.send_message(message)


def send_faculty_credentials_email(
    email: str,
    full_name: str,
    temporary_password: str,
) -> None:
    """
    Send temporary login credentials to an approved faculty member.

    The faculty member is required to change the temporary password after
    the first successful login.
    """

    settings = get_settings()

    body = f"""
Hello {full_name},

Your faculty registration request for CoreSight has been approved.

You can now sign in using the following credentials.

Email:
{email}

Temporary Password:
{temporary_password}

Login here:
{settings.frontend_url}/login

IMPORTANT:

This is a temporary password.

You will be required to create a new password after your first login.

Please do not share these credentials with anyone.

Regards,
CoreSight Administration
""".strip()

    _send_email(
        recipient=email,
        subject="Your CoreSight Faculty Account",
        body=body,
    )


def send_student_credentials_email(
    email: str,
    full_name: str,
    temporary_password: str,
    roll_number: str | None = None,
    batch_name: str | None = None,
) -> None:
    """
    Send initial login credentials to a newly registered student.

    Student account workflow:

        Google Form submission
                |
                v
        Student account created
                |
                v
        Temporary password generated
                |
                v
        Credentials emailed
                |
                v
        Student logs in
                |
                v
        must_change_password = True
                |
                v
        Student creates permanent password
                |
                v
        Student dashboard
                |
                v
        Face enrollment

    roll_number and batch_name are optional so this function remains
    compatible with registration_sync.py while the registration sync
    service is being updated.
    """

    settings = get_settings()

    student_details = ""

    if roll_number:
        student_details += f"""
Roll Number:
{roll_number}
"""

    if batch_name:
        student_details += f"""
Batch:
{batch_name}
"""

    body = f"""
Hello {full_name},

Your CoreSight student account has been created successfully.

Student details:

Name:
{full_name}
{student_details}

Login credentials:

Email:
{email}

Temporary Password:
{temporary_password}

Login here:
{settings.frontend_url}/login

IMPORTANT:

This is a temporary password.

You must create your own password after your first login.

After changing your password, you will be taken to your Student Dashboard.

From the Student Dashboard, you can complete your face enrollment using your camera.

Please do not share your temporary password with anyone.

Regards,
CoreSight Administration
""".strip()

    _send_email(
        recipient=email,
        subject="Your CoreSight Student Account",
        body=body,
    )
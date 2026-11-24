
# src/engine.py

import pandas as pd
import logging
import os
import smtplib
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"

# Ensure output and log directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# Logging configuration
logging.basicConfig(
    filename=LOG_DIR / "automation.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)


def load_contacts():
    """Load contact data from CSV."""
    file_path = DATA_DIR / "contacts.csv"

    if not file_path.exists():
        raise FileNotFoundError("contacts.csv not found in data folder.")

    contacts = pd.read_csv(file_path)
    contacts.columns = contacts.columns.str.strip()

    required = {"contact_id", "name", "email", "department"}
    missing = required - set(contacts.columns)

    if missing:
        raise ValueError(f"Missing columns in contacts.csv: {missing}")

    return contacts


def load_reminders():
    """Load reminder data from CSV."""
    file_path = DATA_DIR / "reminders.csv"

    if not file_path.exists():
        raise FileNotFoundError("reminders.csv not found in data folder.")

    reminders = pd.read_csv(file_path)
    reminders.columns = reminders.columns.str.strip()

    required = {
        "reminder_id", "contact_id", "reminder_title",
        "reminder_date", "reminder_time", "status"
    }
    missing = required - set(reminders.columns)

    if missing:
        raise ValueError(f"Missing columns in reminders.csv: {missing}")

    return reminders


def load_template():
    """Read the email body template."""
    template_path = TEMPLATE_DIR / "reminder_template.txt"

    if not template_path.exists():
        raise FileNotFoundError("reminder_template.txt not found.")

    return template_path.read_text(encoding="utf-8")


def get_reminder_data():
    """Combine reminders with contact information."""
    contacts = load_contacts()
    reminders = load_reminders()

    data = reminders.merge(
        contacts,
        on="contact_id",
        how="left"
    )

    return data


def personalize_message(template, row):
    """Replace template placeholders with actual data."""
    message = template

    fields = {
        "name": row.get("name", "User"),
        "reminder_title": row.get("reminder_title", ""),
        "reminder_date": row.get("reminder_date", ""),
        "reminder_time": row.get("reminder_time", ""),
        "department": row.get("department", "")
    }

    for key, value in fields.items():
        message = message.replace("{" + key + "}", str(value))

    return message


def send_email(recipient, subject, body, dry_run=True):
    """
    Send an email or simulate sending.
    Dry run is enabled by default.
    """

    if dry_run:
        logging.info("DRY RUN | Email simulated for %s", recipient)
        return True, "Simulated successfully"

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]):
        return False, "SMTP configuration missing in .env"

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logging.info("SENT | Email sent to %s", recipient)
        return True, "Email sent successfully"

    except Exception as error:
        logging.error("FAILED | %s | %s", recipient, error)
        return False, str(error)


def process_reminders(dry_run=True, only_pending=True):
    """
    Process reminder records.
    By default, only pending reminders are processed.
    """

    data = get_reminder_data()
    template = load_template()

    if only_pending:
        data = data[data["status"].str.lower() == "pending"]

    results = []

    for _, row in data.iterrows():
        recipient = row.get("email")

        if pd.isna(recipient):
            success = False
            message = "Contact email not found"
        else:
            subject = f"Reminder: {row['reminder_title']}"
            body = personalize_message(template, row)

            success, message = send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                dry_run=dry_run
            )

        result_status = "Sent" if success else "Failed"

        results.append({
            "reminder_id": row["reminder_id"],
            "contact_id": row["contact_id"],
            "name": row.get("name", ""),
            "email": recipient,
            "department": row.get("department", ""),
            "reminder_title": row["reminder_title"],
            "reminder_date": row["reminder_date"],
            "reminder_time": row["reminder_time"],
            "status": result_status,
            "mode": "Dry Run" if dry_run else "Real Email",
            "message": message,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        logging.info(
            "%s | %s | %s",
            result_status,
            row["reminder_id"],
            recipient
        )

    report = pd.DataFrame(results)

    if not report.empty:
        # Save report with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = OUTPUT_DIR / f"report_{timestamp}.csv"
        report.to_csv(report_path, index=False)

        # Save a latest report for easy access
        report.to_csv(OUTPUT_DIR / "latest_report.csv", index=False)

        # Update reminder statuses only for actual email sending.
        # Dry run does not modify source reminder statuses.
        if not dry_run:
            original = load_reminders()
            status_map = report.set_index("reminder_id")["status"].to_dict()
            original["status"] = original.apply(
                lambda r: status_map.get(r["reminder_id"], r["status"]),
                axis=1
            )
            original.to_csv(DATA_DIR / "reminders.csv", index=False)

    return report

def get_due_reminders(now=None):
    """
    Return pending reminders whose scheduled date and time
    have arrived or passed.

    Args:
        now: Optional datetime for testing. Defaults to current time.

    Returns:
        DataFrame containing only due pending reminders.
    """

    if now is None:
        now = datetime.now()

    data = get_reminder_data()

    # Normalize reminder status
    data["status"] = data["status"].astype(str).str.strip().str.title()

    # Combine reminder date and time into a datetime value
    data["scheduled_datetime"] = pd.to_datetime(
        data["reminder_date"].astype(str).str.strip()
        + " "
        + data["reminder_time"].astype(str).str.strip(),
        errors="coerce"
    )

    # Only pending reminders
    pending = data[data["status"] == "Pending"].copy()

    # Only reminders due now or earlier
    due = pending[pending["scheduled_datetime"] <= now].copy()

    # Remove invalid date/time records
    due = due.dropna(subset=["scheduled_datetime"])

    return due

def process_due_reminders(dry_run=True, processed_ids=None):
    """Process only reminders that are due."""

    if processed_ids is None:
        processed_ids = set()

    due = get_due_reminders()
    template = load_template()
    results = []

    for _, row in due.iterrows():
        reminder_id = row["reminder_id"]

        # Avoid processing the same reminder twice in this session
        if reminder_id in processed_ids:
            continue

        recipient = row.get("email")

        if pd.isna(recipient):
            success = False
            message = "Contact email not found"
        else:
            subject = f"Reminder: {row['reminder_title']}"
            body = personalize_message(template, row)

            success, message = send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                dry_run=dry_run
            )

        status = "Sent" if success else "Failed"

        result = {
            "reminder_id": reminder_id,
            "contact_id": row["contact_id"],
            "name": row.get("name", ""),
            "email": recipient,
            "department": row.get("department", ""),
            "reminder_title": row["reminder_title"],
            "reminder_date": row["reminder_date"],
            "reminder_time": row["reminder_time"],
            "status": status,
            "mode": "Dry Run" if dry_run else "Real Email",
            "message": message,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        results.append(result)
        processed_ids.add(reminder_id)

        logging.info(
            "SCHEDULER | %s | %s | %s",
            status,
            reminder_id,
            recipient
        )

    report = pd.DataFrame(results)

    if not report.empty:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = OUTPUT_DIR / f"scheduler_report_{timestamp}.csv"
        report.to_csv(report_path, index=False)

        logging.info("Scheduler report saved: %s", report_path)

    return report
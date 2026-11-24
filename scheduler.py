import schedule
import time
import logging
from pathlib import Path

from src.engine import process_due_reminders

# Create log directory
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "scheduler.log"

# Configure logging (force=True fixes existing logging configuration)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)

processed_ids = set()


def check_due_reminders():
    """Check and process due reminders safely."""

    print("\nChecking for due reminders...")
    logging.info("Scheduler check started")

    try:
        report = process_due_reminders(
            dry_run=True,
            processed_ids=processed_ids
        )

        if report.empty:
            print("No new due reminders found.")
            logging.info("No new due reminders found")

        else:
            print(f"Processed {len(report)} reminders.")
            print(report[["reminder_id", "reminder_title", "status"]])

            logging.info("Processed %s reminders", len(report))

    except Exception as error:
        logging.exception("Scheduler check failed")
        print(f"Scheduler error: {error}")


# Initial check on startup
check_due_reminders()

# Repeat every minute
schedule.every(1).minutes.do(check_due_reminders)

print("\nEmail Reminder Scheduler is running.")
print("Checking every 1 minute.")
print("Mode: DRY RUN (no real emails will be sent)")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        schedule.run_pending()
        time.sleep(1)

except KeyboardInterrupt:
    print("\nScheduler stopped safely by user.")
    logging.info("Scheduler stopped by user")
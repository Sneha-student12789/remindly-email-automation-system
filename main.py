import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from src.engine import (
    load_contacts,
    load_reminders,
    get_reminder_data,
    load_template,
    personalize_message,
    send_email,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Remindly | Automation Workspace",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------- STYLING ----------------
st.markdown("""
<style>
.stApp { background:#0b1120; color:#e2e8f0; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { display:none; }
.block-container { padding-top:1.4rem; max-width:1450px; }
h1,h2,h3 { color:#f8fafc !important; }
p, label { color:#cbd5e1; }
.brand { font-size:29px; font-weight:800; color:#f8fafc; }
.accent { color:#2dd4bf; }
.subbrand { color:#94a3b8; font-size:12px; letter-spacing:2px; }
div[data-testid="stMetric"] {
    background:#151f30; border:1px solid #263449;
    padding:18px; border-radius:13px;
}
div[data-testid="stMetricLabel"] { color:#94a3b8 !important; }
div[data-testid="stMetricValue"] { color:#f8fafc !important; }
div[data-testid="stTabs"] button { color:#94a3b8; font-weight:600; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:#2dd4bf !important; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#2dd4bf !important; }
div[data-testid="stTabs"] [data-baseweb="tab-border"] { background:#263449 !important; }
.stButton button, .stDownloadButton button {
    background:#14b8a6; color:white; border:0;
    border-radius:8px; font-weight:600;
}
.stButton button:hover, .stDownloadButton button:hover {
    background:#0d9488; color:white;
}
input, textarea { background:#151f30 !important; color:#f8fafc !important; }
div[data-testid="stDataFrame"] { border:1px solid #263449; border-radius:10px; }
hr { border-color:#263449; }
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown(
    '<div class="brand">✉ Remind<span class="accent">ly</span></div>'
    '<div class="subbrand">EMAIL AUTOMATION WORKSPACE</div>',
    unsafe_allow_html=True
)
st.write("")

# ---------------- LOAD DATA ----------------
try:
    contacts = load_contacts()
    reminders = load_reminders()
    combined = get_reminder_data()
except Exception as exc:
    st.error(f"Unable to load project data: {exc}")
    st.stop()

contacts = contacts.copy()
reminders = reminders.copy()
combined = combined.copy()

for df in (reminders, combined):
    df["status"] = df["status"].astype(str).str.strip().str.title()

# ---------------- NAVIGATION ----------------
dashboard_tab, contacts_tab, reminders_tab, preview_tab, reports_tab = st.tabs(
    ["⌂  Dashboard", "♙  Contacts", "▦  Reminders", "✉  Email Preview", "▤  Reports"]
)

# Status counts
pending_count = (reminders["status"] == "Pending").sum()
sent_count = (reminders["status"] == "Sent").sum()
failed_count = (reminders["status"] == "Failed").sum()

# ==========================================================
# DASHBOARD
# ==========================================================
with dashboard_tab:
    st.title("Dashboard")
    st.caption("Overview of your reminder operations and contact database.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Contacts", f"{len(contacts):,}")
    k2.metric("Total Reminders", f"{len(reminders):,}")
    k3.metric("Pending Reminders", f"{pending_count:,}")
    k4.metric("Previously Sent", f"{sent_count:,}")

    st.write("")
    left, right = st.columns([1.5, 1])

    with left:
        st.subheader("Reminders by Department")
        dept_counts = combined["department"].fillna("Unknown").value_counts()
        st.bar_chart(dept_counts, color="#2dd4bf", height=300)

    with right:
        st.subheader("Reminder Status")
        status_counts = reminders["status"].value_counts()
        st.bar_chart(status_counts, color="#60a5fa", height=300)
        st.metric("Failed Records", failed_count)

    st.subheader("Upcoming / Recent Reminders")
    recent = combined[
        ["name", "department", "reminder_title", "reminder_date", "reminder_time", "status"]
    ].head(10).copy()
    recent.columns = ["Contact", "Department", "Reminder", "Date", "Time", "Status"]
    st.dataframe(recent, use_container_width=True, hide_index=True)

    st.subheader("Automation Center")
    st.info("Safe simulation mode is enabled. No real email will be sent from this action.")

    if st.button("▶  Simulate All Pending Reminders", key="simulate_all"):
        try:
            template = load_template()
            pending = combined[combined["status"] == "Pending"].copy()
            results = []

            for _, row in pending.iterrows():
                recipient = row.get("email")
                if pd.isna(recipient) or not recipient:
                    ok, msg = False, "Missing contact email"
                else:
                    body = personalize_message(template, row)
                    subject = f"Reminder: {row['reminder_title']}"
                    ok, msg = send_email(recipient, subject, body, dry_run=True)

                results.append({
                    "reminder_id": row["reminder_id"],
                    "contact_id": row["contact_id"],
                    "name": row.get("name", ""),
                    "email": recipient,
                    "reminder_title": row["reminder_title"],
                    "status": "Simulated" if ok else "Failed",
                    "mode": "Dry Run",
                    "message": msg,
                    "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            result_df = pd.DataFrame(results)
            if not result_df.empty:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_file = OUTPUT_DIR / f"simulation_{stamp}.csv"
                result_df.to_csv(report_file, index=False)
                result_df.to_csv(OUTPUT_DIR / "latest_report.csv", index=False)

            st.success(f"Simulation finished. {len(results)} reminders processed.")
            if results:
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                st.info("No pending reminders to simulate.")

        except Exception as exc:
            st.error(f"Simulation error: {exc}")

# ==========================================================
# CONTACTS
# ==========================================================
with contacts_tab:
    st.title("Contact Directory")
    st.caption("Browse, search and export your contact database.")

    st.metric("Total Registered Contacts", len(contacts))
    c_search, c_dept = st.columns([2, 1])

    with c_search:
        search = st.text_input("Search", placeholder="Name, email or contact ID")

    with c_dept:
        dept_list = sorted(contacts["department"].dropna().unique().tolist())
        selected_dept = st.selectbox("Department", ["All Departments"] + dept_list)

    filtered_contacts = contacts.copy()

    if search:
        search_mask = (
            filtered_contacts["name"].astype(str).str.contains(search, case=False, na=False)
            | filtered_contacts["email"].astype(str).str.contains(search, case=False, na=False)
            | filtered_contacts["contact_id"].astype(str).str.contains(search, case=False, na=False)
        )
        filtered_contacts = filtered_contacts[search_mask]

    if selected_dept != "All Departments":
        filtered_contacts = filtered_contacts[
            filtered_contacts["department"] == selected_dept
        ]

    st.caption(f"{len(filtered_contacts)} contact(s) found")
    st.dataframe(filtered_contacts, use_container_width=True, hide_index=True)

    st.download_button(
        "↓  Export Contacts",
        filtered_contacts.to_csv(index=False).encode("utf-8"),
        "contacts_export.csv",
        "text/csv"
    )

# ==========================================================
# REMINDERS
# ==========================================================
with reminders_tab:
    st.title("Reminder Management")
    st.caption("Filter and inspect your scheduled reminders.")

    a, b, c, d = st.columns(4)
    a.metric("All", len(reminders))
    b.metric("Pending", pending_count)
    c.metric("Sent", sent_count)
    d.metric("Failed", failed_count)

    r_search, r_status = st.columns([2, 1])

    with r_search:
        reminder_search = st.text_input("Search reminder", placeholder="Title or contact ID")

    with r_status:
        status_filter = st.selectbox(
            "Status filter", ["All Statuses", "Pending", "Sent", "Failed"]
        )

    view = reminders.copy()

    if status_filter != "All Statuses":
        view = view[view["status"] == status_filter]

    if reminder_search:
        view = view[
            view["reminder_title"].astype(str).str.contains(reminder_search, case=False, na=False)
            | view["contact_id"].astype(str).str.contains(reminder_search, case=False, na=False)
        ]

    st.caption(f"{len(view)} reminder(s) displayed")
    st.dataframe(view, use_container_width=True, hide_index=True)

    st.download_button(
        "↓  Export Reminders",
        view.to_csv(index=False).encode("utf-8"),
        "reminders_export.csv",
        "text/csv"
    )

# ==========================================================
# EMAIL PREVIEW + SINGLE REMINDER SIMULATION
# ==========================================================
# ==========================================================
# EMAIL PREVIEW + SINGLE REMINDER SIMULATION
# ==========================================================
with preview_tab:
    import html

    st.title("Email Preview")
    st.caption("Review, customize, and verify your email before processing.")

    if combined.empty:
        st.warning("No reminder records are available.")

    else:
        reminder_ids = combined["reminder_id"].astype(str).tolist()
        chosen_id = st.selectbox("Select Reminder", reminder_ids)

        row = combined[
            combined["reminder_id"].astype(str) == chosen_id
        ].iloc[0]

        template = load_template()
        original_body = personalize_message(template, row)

        # Clean HTML entities and unwanted whitespace
        original_body = html.unescape(original_body)
        original_body = original_body.replace("\xa0", " ")
        original_body = original_body.replace("&#x20;", " ")

        import re

        original_body = re.sub(r"[ \t]+", " ", original_body)
        original_body = re.sub(r" *\n *", "\n", original_body)
        original_body = re.sub(r"\n{3,}", "\n\n", original_body)
        original_body = original_body.strip()
        original_subject = f"Reminder: {row['reminder_title']}"

        # Unique editable fields for each reminder
        subject_key = f"email_subject_{chosen_id}"
        body_key = f"email_body_{chosen_id}"

        # Initialize values only once
        if subject_key not in st.session_state:
            st.session_state[subject_key] = original_subject

        if body_key not in st.session_state:
            st.session_state[body_key] = original_body

        st.markdown("### Recipient Details")

        col1, col2 = st.columns(2)

        col1.text_input(
            "Recipient Name",
            value=str(row.get("name", "")),
            disabled=True
        )

        col2.text_input(
            "Recipient Email",
            value=str(row.get("email", "")),
            disabled=True
        )

        st.markdown("### Customize Email")

        # Reset before editable widgets are created
        if st.button("↺ Reset to Original Template", key=f"reset_{chosen_id}"):
            st.session_state[subject_key] = original_subject
            st.session_state[body_key] = original_body

        edited_subject = st.text_input(
            "Email Subject",
            key=subject_key
        )

        edited_body = st.text_area(
            "Email Message",
            key=body_key,
            height=250
        )

        st.caption("You can edit the subject and message above. Changes are reflected in the preview.")

        # ---------------- LIVE PREVIEW ----------------
        st.markdown("### Live Email Preview")

        safe_subject = html.escape(edited_subject)
        safe_body = html.escape(edited_body)

       
        email_preview_html = f"""
        <div style="background:#ffffff;
                    border-radius:14px;
                    overflow:hidden;
                    border:1px solid #dbe2ea;
                    font-family:Arial,sans-serif;
                    margin:10px 0;">

            <div style="background:#f1f5f9;
                        padding:18px 22px;
                        border-bottom:1px solid #e2e8f0;">
                <div style="font-size:18px;
                            font-weight:bold;
                            color:#0f172a;">
                    Remindly
                </div>
                <div style="font-size:12px;
                            color:#64748b;
                            margin-top:4px;">
                    Automated Reminder System
                </div>
            </div>

            <div style="padding:22px;">

                <div style="color:#64748b;font-size:12px;">FROM</div>
                <div style="color:#334155;margin-bottom:14px;">
                    Remindly Automation System
                </div>

                <div style="color:#64748b;font-size:12px;">TO</div>
                <div style="color:#334155;margin-bottom:14px;">
                    {html.escape(str(row.get("email", "")))}
                </div>

                <div style="color:#64748b;font-size:12px;">SUBJECT</div>
                <div style="color:#0f172a;
                            font-weight:bold;
                            font-size:18px;
                            margin:6px 0 20px;">
                    {safe_subject}
                </div>

                <hr style="border:0;border-top:1px solid #e2e8f0;">

                <div style="color:#334155;
                font-size:14px;
                white-space:pre-wrap;
                line-height:1.8;
                padding-top:15px;">{safe_body}</div>

            </div>

            <div style="background:#f8fafc;
                        border-top:1px solid #e2e8f0;
                        padding:14px 22px;
                        color:#64748b;
                        font-size:12px;">
                This email was generated automatically by Remindly.
                Please do not reply to this email.
            </div>
        </div>
        """

        st.html(email_preview_html)
        

        st.caption(
            f"Reminder ID: {chosen_id}  |  "
            f"Current Status: {row['status']}"
        )

        st.info("Processing is currently in Dry Run mode. No real emails will be sent.")

        # ---------------- PROCESS CUSTOMIZED EMAIL ----------------
        if st.button(
            "▶ Process Customized Email (Simulation)",
            key=f"process_custom_{chosen_id}"
        ):
            try:
                recipient = row.get("email")

                if pd.isna(recipient) or not recipient:
                    st.error("This contact has no email address.")

                elif not edited_subject.strip() or not edited_body.strip():
                    st.error("Subject and message cannot be empty.")

                else:
                    success, message = send_email(
                        recipient=recipient,
                        subject=edited_subject,
                        body=edited_body,
                        dry_run=True
                    )

                    result = pd.DataFrame([{
                        "reminder_id": row["reminder_id"],
                        "contact_id": row["contact_id"],
                        "name": row.get("name", ""),
                        "email": recipient,
                        "department": row.get("department", ""),
                        "reminder_title": row["reminder_title"],
                        "reminder_date": row["reminder_date"],
                        "reminder_time": row["reminder_time"],
                        "subject": edited_subject,
                        "status": "Simulated" if success else "Failed",
                        "mode": "Dry Run",
                        "message": message,
                        "processed_at": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    }])

                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    result.to_csv(
                        OUTPUT_DIR / f"single_simulation_{stamp}.csv",
                        index=False
                    )

                    result.to_csv(
                        OUTPUT_DIR / "latest_report.csv",
                        index=False
                    )

                    if success:
                        st.success(
                            "Simulation successful! "
                            "Your customized email was processed. "
                            "No real email was sent."
                        )

                        st.dataframe(
                            result,
                            use_container_width=True,
                            hide_index=True
                        )

                    else:
                        st.error(message)

            except Exception as exc:
                st.error(f"Processing error: {exc}")

# ==========================================================
# REPORTS
# ==========================================================
with reports_tab:
    st.title("Reports & Analytics")
    st.caption("Review simulation history, outcomes and downloadable reports.")

    # Collect CSV reports
    all_csv_files = sorted(
        OUTPUT_DIR.glob("*.csv"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    # Exclude latest_report.csv from analytics to avoid counting
    # the duplicate copy of the most recent report
    history_files = [
        f for f in all_csv_files
        if f.name.lower() != "latest_report.csv"
    ]

    report_data = []

    for file in history_files:
        try:
            df = pd.read_csv(file)
            if not df.empty:
                report_data.append((file, df))
        except Exception as exc:
            st.warning(f"Could not read report {file.name}: {exc}")

    # ---------------- ANALYTICS ----------------
    st.subheader("Simulation Analytics")

    if report_data:
        all_reports = pd.concat(
            [df for _, df in report_data],
            ignore_index=True
        )

        total_processed = len(all_reports)


        # Use the latest processing result for each unique reminder
        analytics_reports = all_reports.copy()

        if "processed_at" in analytics_reports.columns:
            analytics_reports["_processed_time"] = pd.to_datetime(
                analytics_reports["processed_at"],
                errors="coerce"
            )

            analytics_reports = analytics_reports.sort_values(
                "_processed_time",
                na_position="first"
            )

        if "reminder_id" in analytics_reports.columns:
            analytics_reports = analytics_reports.drop_duplicates(
                subset="reminder_id",
                keep="last"
            )

        # Count only records that have actually been processed
        status_values = (
            analytics_reports["status"].astype(str).str.strip().str.lower()
        )

        processed_statuses = ["simulated", "sent", "failed"]

        processed_reports = analytics_reports[
            status_values.isin(processed_statuses)
        ]

        total_processed = len(processed_reports)

        successful_count = (
            processed_reports["status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["simulated", "sent"])
            .sum()
        )

        failed_report_count = (
            processed_reports["status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("failed")
            .sum()
        )

        simulated_count = successful_count

        success_rate = (
            (successful_count / total_processed) * 100
            if total_processed else 0
        )

        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Processed", total_processed)
        m2.metric("Successful Runs", simulated_count)        
        m3.metric("Failed Records", failed_report_count)
        m4.metric("Success Rate", f"{success_rate:.1f}%")

        st.caption(
            "Analytics are calculated from timestamped reports. "
            "latest_report.csv is excluded to avoid duplicate counting."
        )
    else:
        st.info("No simulation history available yet. Run a simulation first.")

    st.divider()

    # ---------------- REPORT HISTORY ----------------
    st.subheader("Report History")

    # Allow latest_report.csv to be viewed, but not included in analytics
    viewable_files = all_csv_files

    if viewable_files:
        selected_file = st.selectbox(
            "Select a report to view",
            [f.name for f in viewable_files]
        )

        selected_path = next(
            f for f in viewable_files if f.name == selected_file
        )

        try:
            selected_df = pd.read_csv(selected_path)

            st.caption(f"Selected file: {selected_file}")
            st.dataframe(
                selected_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "↓  Download Selected Report",
                selected_df.to_csv(index=False).encode("utf-8"),
                selected_file,
                "text/csv",
                key="download_selected_report"
            )

        except Exception as exc:
            st.error(f"Unable to display selected report: {exc}")

    else:
        st.info("No report files found in the outputs folder.")

    # ---------------- AUTOMATION LOG ----------------
    log_file = LOG_DIR / "automation.log"

    if log_file.exists():
        with st.expander("Automation Log"):
            log_content = log_file.read_text(
                encoding="utf-8",
                errors="replace"
            )
            st.text(log_content[-4000:])
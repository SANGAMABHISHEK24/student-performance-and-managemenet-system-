import streamlit as st
import pandas as pd
import hashlib
import plotly.express as px
from datetime import datetime, date

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Student Performance & Management System",
    page_icon="🎓",
    layout="wide",
)

DB_PATH = "students.db"

# ----------------------------------------------------------------------------
# AUTH CONFIG
# ----------------------------------------------------------------------------
# Production credentials are stored in Streamlit Secrets.
# Required secrets:
#   ADMIN_USERNAME
#   ADMIN_PASSWORD
#   TURSO_DATABASE_URL
#   TURSO_AUTH_TOKEN
# ----------------------------------------------------------------------------

import os
import hmac
import libsql


def _secret(name: str, default=None):
    """Read a value from Streamlit Secrets, with environment fallback."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None

    if value is not None and str(value).strip():
        return value

    return os.getenv(name, default)


TURSO_DATABASE_URL = _secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _secret("TURSO_AUTH_TOKEN")


def check_login(username: str, password: str) -> bool:
    configured_username = str(_secret("ADMIN_USERNAME", "admin"))
    configured_password = str(_secret("ADMIN_PASSWORD", ""))

    if not configured_password:
        return False

    return (
        hmac.compare_digest(username, configured_username)
        and hmac.compare_digest(password, configured_password)
    )


# ----------------------------------------------------------------------------
# DATABASE LAYER (Turso / libSQL)
# ----------------------------------------------------------------------------

def get_connection():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise RuntimeError(
            "Turso credentials are missing. Configure "
            "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in Streamlit Secrets."
        )

    return libsql.connect(
        database=TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN,
    )


def _rows_to_dataframe(cursor, columns):
    return pd.DataFrame(cursor.fetchall(), columns=columns)


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                grade TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                attendance INTEGER NOT NULL CHECK(attendance >= 0 AND attendance <= 100),
                created_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_name TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                attendance_pct INTEGER NOT NULL CHECK(attendance_pct >= 0 AND attendance_pct <= 100),
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_subjects_student_id "
            "ON subjects(student_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_student_id "
            "ON attendance_log(student_id)"
        )

        conn.commit()
    finally:
        conn.close()


def fetch_all_students() -> pd.DataFrame:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id AS ID, name AS Name, grade AS Grade, score AS Score, "
            "attendance AS 'Attendance (%)' FROM students ORDER BY id ASC"
        )
        return _rows_to_dataframe(
            cur, ["ID", "Name", "Grade", "Score", "Attendance (%)"]
        )
    finally:
        conn.close()


def insert_student(student_id, name, grade, score, attendance):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students "
            "(id, name, grade, score, attendance, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (student_id, name, grade, score, attendance, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_student(student_id, name, grade, score, attendance):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE students SET name=?, grade=?, score=?, attendance=? WHERE id=?",
            (name, grade, score, attendance, student_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_student(student_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM subjects WHERE student_id=?", (student_id,))
        cur.execute("DELETE FROM attendance_log WHERE student_id=?", (student_id,))
        cur.execute("DELETE FROM students WHERE id=?", (student_id,))
        conn.commit()
    finally:
        conn.close()


def student_id_exists(student_id) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM students WHERE id=? LIMIT 1", (student_id,))
        return cur.fetchone() is not None
    finally:
        conn.close()


def fetch_subjects(student_id=None) -> pd.DataFrame:
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = (
            "SELECT s.id, s.student_id, st.name AS student_name, "
            "s.subject_name, s.score "
            "FROM subjects s JOIN students st ON s.student_id = st.id "
        )

        if student_id is not None:
            query += "WHERE s.student_id = ? ORDER BY s.subject_name"
            cur.execute(query, (student_id,))
        else:
            query += "ORDER BY st.name, s.subject_name"
            cur.execute(query)

        return _rows_to_dataframe(
            cur, ["id", "student_id", "student_name", "subject_name", "score"]
        )
    finally:
        conn.close()


def add_subject_score(student_id, subject_name, score):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO subjects (student_id, subject_name, score) VALUES (?, ?, ?)",
            (student_id, subject_name, score),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_attendance_log(student_id=None) -> pd.DataFrame:
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = (
            "SELECT a.id, a.student_id, st.name AS student_name, "
            "a.log_date, a.attendance_pct "
            "FROM attendance_log a JOIN students st ON a.student_id = st.id "
        )

        if student_id is not None:
            query += "WHERE a.student_id = ? ORDER BY a.log_date"
            cur.execute(query, (student_id,))
        else:
            query += "ORDER BY st.name, a.log_date"
            cur.execute(query)

        return _rows_to_dataframe(
            cur, ["id", "student_id", "student_name", "log_date", "attendance_pct"]
        )
    finally:
        conn.close()


def add_attendance_record(student_id, log_date, attendance_pct):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO attendance_log "
            "(student_id, log_date, attendance_pct) VALUES (?, ?, ?)",
            (student_id, log_date, attendance_pct),
        )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------
def calculate_grade(score: int) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    else:
        return "F"

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# ----------------------------------------------------------------------------
# INIT DB
# ----------------------------------------------------------------------------
init_db()

# ----------------------------------------------------------------------------
# LOGIN GATE
# ----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🎓 Student Performance & Management System")
    st.subheader("🔐 Admin Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Login")

        if login_submitted:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

    st.caption("Admin credentials are configured securely through Streamlit Secrets.")
    st.stop()

# ----------------------------------------------------------------------------
# SIDEBAR NAVIGATION (only reachable when logged in)
# ----------------------------------------------------------------------------
st.sidebar.title("🎓 Navigation")
st.sidebar.caption(f"Logged in as **{st.session_state.get('username', 'admin')}**")

page = st.sidebar.radio(
    "Go to",
    [
        "Dashboard",
        "Student Directory",
        "Student Profile",
        "Add New Student",
        "Edit / Delete Student",
        "Subjects & Charts",
        "Attendance History",
        "Bulk Import (CSV)",
    ],
)

df_sidebar = fetch_all_students()
st.sidebar.markdown("---")
st.sidebar.caption(f"📊 Database currently holds **{len(df_sidebar)}** student record(s).")
st.sidebar.caption("☁️ Data stored persistently in Turso (libSQL).")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ----------------------------------------------------------------------------
# PAGE 1: DASHBOARD
# ----------------------------------------------------------------------------
if page == "Dashboard":
    st.title("📊 Student Performance Dashboard")
    st.markdown("Overview of student performance and attendance metrics.")

    df = fetch_all_students()

    if df.empty:
        st.warning("No student data available. Add students from the sidebar.")
    else:
        total_students = len(df)
        avg_score = df["Score"].mean()
        avg_attendance = df["Attendance (%)"].mean()
        top_student = df.loc[df["Score"].idxmax(), "Name"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Students", f"{total_students}")
        col2.metric("Average Score", f"{avg_score:.1f}")
        col3.metric("Average Attendance", f"{avg_attendance:.1f}%")
        col4.metric("Top Performer", top_student)

        st.markdown("---")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Scores by Student")
            fig_bar = px.bar(
                df, x="Name", y="Score", color="Grade",
                color_discrete_map={"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "F": "#e74c3c"},
                text="Score",
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(showlegend=True, yaxis_range=[0, 110])
            st.plotly_chart(fig_bar, use_container_width=True)

        with chart_col2:
            st.subheader("Attendance by Student")
            fig_line = px.line(df, x="Name", y="Attendance (%)", markers=True)
            fig_line.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("---")
        st.subheader("Grade Distribution")
        grade_counts = df["Grade"].value_counts().reset_index()
        grade_counts.columns = ["Grade", "Count"]
        fig_pie = px.pie(
            grade_counts, names="Grade", values="Count", hole=0.4,
            color="Grade",
            color_discrete_map={"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "F": "#e74c3c"},
        )
        st.plotly_chart(fig_pie, use_container_width=True)


        st.markdown("---")
        st.subheader("⚠️ Students Needing Attention")

        at_risk = df[(df["Score"] < 60) | (df["Attendance (%)"] < 75)].copy()

        if at_risk.empty:
            st.success("No students currently meet the attention criteria.")
        else:
            at_risk["Reason"] = at_risk.apply(
                lambda row: (
                    "Low score & attendance"
                    if row["Score"] < 60 and row["Attendance (%)"] < 75
                    else "Low score"
                    if row["Score"] < 60
                    else "Low attendance"
                ),
                axis=1,
            )
            st.dataframe(
                at_risk[
                    ["ID", "Name", "Grade", "Score", "Attendance (%)", "Reason"]
                ],
                use_container_width=True,
                hide_index=True,
            )

# ----------------------------------------------------------------------------
# PAGE 2: STUDENT DIRECTORY
# ----------------------------------------------------------------------------
elif page == "Student Directory":
    st.title("📋 Student Directory")
    st.markdown("Search, filter, and export the full student list.")

    df = fetch_all_students()

    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_term = st.text_input("🔍 Search by name or ID")
    with col_filter:
        grade_filter = st.multiselect("Filter by grade", options=["A", "B", "C", "F"])

    filtered_df = df.copy()
    if search_term:
        filtered_df = filtered_df[
            filtered_df["Name"].str.contains(search_term, case=False, na=False)
            | filtered_df["ID"].astype(str).str.contains(search_term)
        ]
    if grade_filter:
        filtered_df = filtered_df[filtered_df["Grade"].isin(grade_filter)]

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(filtered_df)} of {len(df)} students")

    st.markdown("---")
    csv_data = convert_df_to_csv(filtered_df)
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv_data,
        file_name="student_directory.csv",
        mime="text/csv",
    )

# ----------------------------------------------------------------------------
# PAGE 3: STUDENT PROFILE
# ----------------------------------------------------------------------------
elif page == "Student Profile":
    st.title("👨‍🎓 Student Profile")
    st.markdown(
        "View a complete performance, subject and attendance summary for one student."
    )

    df = fetch_all_students()

    if df.empty:
        st.warning("No students in the database yet. Add a student first.")
    else:
        selected_profile_id = st.selectbox(
            "Select Student",
            options=df["ID"].tolist(),
            format_func=lambda x: (
                f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}"
            ),
            key="profile_student_id",
        )

        student = df[df["ID"] == selected_profile_id].iloc[0]
        subjects_df = fetch_subjects(selected_profile_id)
        attendance_df = fetch_attendance_log(selected_profile_id)

        st.markdown("---")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Student ID", str(student["ID"]))
        c2.metric("Grade", student["Grade"])
        c3.metric("Overall Score", f'{student["Score"]}/100')
        c4.metric("Attendance", f'{student["Attendance (%)"]}%')

        st.subheader(f'📋 {student["Name"]}')

        info_col, chart_col = st.columns([1, 2])

        with info_col:
            st.markdown("### Student Information")
            st.write(f'**Name:** {student["Name"]}')
            st.write(f'**Student ID:** {student["ID"]}')
            st.write(f'**Grade:** {student["Grade"]}')
            st.write(f'**Overall Score:** {student["Score"]}')
            st.write(f'**Attendance:** {student["Attendance (%)"]}%')

            if student["Score"] >= 90 and student["Attendance (%)"] >= 90:
                st.success("🌟 Excellent overall performance")
            elif student["Score"] < 60 or student["Attendance (%)"] < 75:
                st.warning("⚠️ Student may need academic or attendance support")
            else:
                st.info("ℹ️ Student is performing within the normal range")

        with chart_col:
            st.markdown("### Subject Performance")

            if subjects_df.empty:
                st.info("No subject scores recorded for this student.")
            else:
                fig_profile = px.bar(
                    subjects_df,
                    x="subject_name",
                    y="score",
                    text="score",
                    color="subject_name",
                )
                fig_profile.update_traces(textposition="outside")
                fig_profile.update_layout(
                    yaxis_range=[0, 110],
                    xaxis_title="Subject",
                    yaxis_title="Score",
                    showlegend=False,
                )
                st.plotly_chart(fig_profile, use_container_width=True)

        st.markdown("---")
        st.subheader("🗓️ Attendance History")

        if attendance_df.empty:
            st.info("No attendance history recorded for this student.")
        else:
            attendance_df = attendance_df.sort_values("log_date")
            fig_att_profile = px.line(
                attendance_df,
                x="log_date",
                y="attendance_pct",
                markers=True,
            )
            fig_att_profile.update_layout(
                yaxis_range=[0, 100],
                xaxis_title="Date",
                yaxis_title="Attendance (%)",
            )
            st.plotly_chart(fig_att_profile, use_container_width=True)

        st.markdown("---")
        st.subheader("📚 Subject Details")

        if subjects_df.empty:
            st.info("No subject details available.")
        else:
            st.dataframe(
                subjects_df[["subject_name", "score"]].rename(
                    columns={"subject_name": "Subject", "score": "Score"}
                ),
                use_container_width=True,
                hide_index=True,
            )

# ----------------------------------------------------------------------------
# PAGE 4: ADD NEW STUDENT
# ----------------------------------------------------------------------------
elif page == "Add New Student":
    st.title("➕ Add New Student")
    st.markdown("Fill out the form below to register a new student.")

    with st.form("add_student_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_id = st.number_input("Student ID", min_value=1, step=1, format="%d")
            new_name = st.text_input("Full Name")
        with col2:
            new_score = st.slider("Score", min_value=0, max_value=100, value=75)
            new_attendance = st.slider("Attendance (%)", min_value=0, max_value=100, value=85)

        submitted = st.form_submit_button("Add Student")

        if submitted:
            if not new_name.strip():
                st.error("⚠️ Please enter a valid student name.")
            elif student_id_exists(int(new_id)):
                st.error(f"⚠️ A student with ID {int(new_id)} already exists. Please use a unique ID.")
            else:
                new_grade = calculate_grade(new_score)
                insert_student(int(new_id), new_name.strip(), new_grade, new_score, new_attendance)
                st.success(f"✅ Student **{new_name}** added successfully with grade **{new_grade}**!")
                st.cache_data.clear()

# ----------------------------------------------------------------------------
# PAGE 5: EDIT / DELETE STUDENT
# ----------------------------------------------------------------------------
elif page == "Edit / Delete Student":
    st.title("✏️ Edit / Delete Student")
    st.markdown("Select a student to update their details or remove them from the database.")

    df = fetch_all_students()

    if df.empty:
        st.warning("No students in the database yet.")
    else:
        selected_id = st.selectbox(
            "Select Student",
            options=df["ID"].tolist(),
            format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}",
        )

        student_row = df[df["ID"] == selected_id].iloc[0]

        with st.form("edit_student_form"):
            col1, col2 = st.columns(2)
            with col1:
                edit_name = st.text_input("Full Name", value=student_row["Name"])
            with col2:
                edit_score = st.slider("Score", 0, 100, int(student_row["Score"]))
                edit_attendance = st.slider("Attendance (%)", 0, 100, int(student_row["Attendance (%)"]))

            col_update, col_delete = st.columns(2)
            update_clicked = col_update.form_submit_button("💾 Update Student", use_container_width=True)
            delete_clicked = col_delete.form_submit_button("🗑️ Delete Student", use_container_width=True)

            if update_clicked:
                if not edit_name.strip():
                    st.error("⚠️ Name cannot be empty.")
                else:
                    edit_grade = calculate_grade(edit_score)
                    update_student(int(selected_id), edit_name.strip(), edit_grade, edit_score, edit_attendance)
                    st.success(f"✅ Student **{edit_name}** updated successfully! New grade: **{edit_grade}**")
                    st.cache_data.clear()
                    st.rerun()

            if delete_clicked:
                delete_student(int(selected_id))
                st.success(f"🗑️ Student ID {selected_id} deleted successfully.")
                st.cache_data.clear()
                st.rerun()

# ----------------------------------------------------------------------------
# PAGE 6: SUBJECTS & CHARTS
# ----------------------------------------------------------------------------
elif page == "Subjects & Charts":
    st.title("📚 Subjects & Per-Subject Performance")
    st.markdown("Track individual subject scores per student and view breakdowns.")

    df = fetch_all_students()

    if df.empty:
        st.warning("No students in the database yet. Add a student first.")
    else:
        st.subheader("➕ Add a Subject Score")
        with st.form("add_subject_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                subj_student_id = st.selectbox(
                    "Student",
                    options=df["ID"].tolist(),
                    format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}",
                )
            with col2:
                subj_name = st.text_input("Subject Name", placeholder="e.g. Math")
            with col3:
                subj_score = st.slider("Subject Score", 0, 100, 75)

            subj_submitted = st.form_submit_button("Add Subject Score")
            if subj_submitted:
                if not subj_name.strip():
                    st.error("⚠️ Please enter a subject name.")
                else:
                    add_subject_score(int(subj_student_id), subj_name.strip(), subj_score)
                    st.success(f"✅ Added {subj_name} score for the selected student.")
                    st.rerun()

        st.markdown("---")

        st.subheader("📈 Per-Student Subject Breakdown")
        chart_student_id = st.selectbox(
            "Select a student to view their subject chart",
            options=df["ID"].tolist(),
            format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}",
            key="subject_chart_student",
        )
        subj_df = fetch_subjects(chart_student_id)

        if subj_df.empty:
            st.info("No subject scores recorded yet for this student.")
        else:
            fig = px.bar(
                subj_df, x="subject_name", y="score", color="subject_name",
                text="score", title=None,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(yaxis_range=[0, 110], xaxis_title="Subject", yaxis_title="Score", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                subj_df[["subject_name", "score"]].rename(columns={"subject_name": "Subject", "score": "Score"}),
                use_container_width=True, hide_index=True,
            )

        st.markdown("---")
        st.subheader("🏫 Class-Wide Average by Subject")
        all_subj_df = fetch_subjects()
        if all_subj_df.empty:
            st.info("No subject data recorded yet across any students.")
        else:
            avg_by_subject = all_subj_df.groupby("subject_name")["score"].mean().reset_index()
            avg_by_subject.columns = ["Subject", "Average Score"]
            fig2 = px.bar(avg_by_subject, x="Subject", y="Average Score", text="Average Score", color="Subject")
            fig2.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig2.update_layout(yaxis_range=[0, 110], showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

# ----------------------------------------------------------------------------
# PAGE 7: ATTENDANCE HISTORY
# ----------------------------------------------------------------------------
elif page == "Attendance History":
    st.title("🗓️ Attendance History Over Time")
    st.markdown("Log daily/periodic attendance and track trends per student.")

    df = fetch_all_students()

    if df.empty:
        st.warning("No students in the database yet. Add a student first.")
    else:
        st.subheader("➕ Log an Attendance Record")
        with st.form("add_attendance_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                att_student_id = st.selectbox(
                    "Student",
                    options=df["ID"].tolist(),
                    format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}",
                )
            with col2:
                att_date = st.date_input("Date", value=date.today())
            with col3:
                att_pct = st.slider("Attendance (%)", 0, 100, 90)

            att_submitted = st.form_submit_button("Add Record")
            if att_submitted:
                add_attendance_record(int(att_student_id), att_date.isoformat(), att_pct)
                st.success("✅ Attendance record added.")
                st.rerun()

        st.markdown("---")

        st.subheader("📉 Attendance Trend Per Student")
        trend_student_id = st.selectbox(
            "Select a student",
            options=df["ID"].tolist(),
            format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Name'].values[0]}",
            key="attendance_chart_student",
        )
        att_df = fetch_attendance_log(trend_student_id)

        if att_df.empty:
            st.info("No attendance history recorded yet for this student.")
        else:
            att_df = att_df.sort_values("log_date")
            fig = px.line(att_df, x="log_date", y="attendance_pct", markers=True)
            fig.update_layout(yaxis_range=[0, 100], xaxis_title="Date", yaxis_title="Attendance (%)")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                att_df[["log_date", "attendance_pct"]].rename(
                    columns={"log_date": "Date", "attendance_pct": "Attendance (%)"}
                ),
                use_container_width=True, hide_index=True,
            )

# ----------------------------------------------------------------------------
# PAGE 8: BULK IMPORT (CSV)
# ----------------------------------------------------------------------------
elif page == "Bulk Import (CSV)":
    st.title("📥 Bulk Import Students via CSV")
    st.markdown(
        "Upload a CSV file with columns: **ID, Name, Score, Attendance**. "
        "Grade is calculated automatically."
    )

    st.info("💡 Don't have a file ready? Download a template below to see the expected format.")
    template_df = pd.DataFrame(
        {"ID": [201, 202], "Name": ["Sample Student A", "Sample Student B"], "Score": [88, 72], "Attendance": [90, 76]}
    )
    st.download_button(
        "⬇️ Download CSV Template",
        data=convert_df_to_csv(template_df),
        file_name="student_import_template.csv",
        mime="text/csv",
    )

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            import_df = pd.read_csv(uploaded_file)
            required_cols = {"ID", "Name", "Score", "Attendance"}

            if not required_cols.issubset(set(import_df.columns)):
                st.error(f"⚠️ CSV must contain these columns: {', '.join(required_cols)}")
            else:
                st.write("Preview of uploaded data:")
                st.dataframe(import_df, use_container_width=True, hide_index=True)

                if st.button("✅ Confirm and Import"):
                    added, skipped = 0, 0
                    for _, row in import_df.iterrows():
                        sid = int(row["ID"])
                        name = str(row["Name"]).strip()
                        score = int(row["Score"])
                        attendance = int(row["Attendance"])

                        if not name or student_id_exists(sid):
                            skipped += 1
                            continue

                        grade = calculate_grade(score)
                        insert_student(sid, name, grade, score, attendance)
                        added += 1

                    st.cache_data.clear()
                    st.success(f"✅ Import complete: {added} student(s) added, {skipped} skipped (duplicate ID or missing name).")
        except Exception as e:
            st.error(f"⚠️ Could not process file: {e}")

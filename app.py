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
# STYLE / PERFORMANCE HELPERS
# ----------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp {
        background: #f5f7fb;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #1e293b 100%);
    }

    [data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }

    .hero {
        padding: 28px 30px;
        border-radius: 20px;
        background: linear-gradient(135deg, #111827 0%, #334155 100%);
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, .12);
    }

    .hero h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 750;
    }

    .hero p {
        margin: 8px 0 0;
        color: #cbd5e1;
    }

    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin: 8px 0 12px;
        color: #0f172a;
    }

    .metric-card {
        padding: 18px;
        border-radius: 16px;
        background: white;
        border: 1px solid #e2e8f0;
        box-shadow: 0 5px 18px rgba(15, 23, 42, .06);
    }

    .metric-label {
        font-size: .82rem;
        color: #64748b;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 1.65rem;
        font-weight: 750;
        color: #0f172a;
    }

    .metric-note {
        font-size: .78rem;
        color: #64748b;
        margin-top: 4px;
    }

    .profile-header {
        padding: 20px;
        border-radius: 18px;
        background: white;
        border: 1px solid #e2e8f0;
        box-shadow: 0 5px 18px rgba(15, 23, 42, .06);
        margin-bottom: 16px;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e2e8f0;
        padding: 14px;
        border-radius: 15px;
        box-shadow: 0 5px 18px rgba(15, 23, 42, .05);
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }

    .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=30, show_spinner=False)
def cached_students():
    return fetch_all_students()


@st.cache_data(ttl=30, show_spinner=False)
def cached_subjects(student_id=None):
    return fetch_subjects(student_id)


@st.cache_data(ttl=30, show_spinner=False)
def cached_attendance(student_id=None):
    return fetch_attendance_log(student_id)


def invalidate_data_cache():
    cached_students.clear()
    cached_subjects.clear()
    cached_attendance.clear()
    st.cache_data.clear()


def metric_card(label, value, note=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title, subtitle):
    st.markdown(
        f"""
        <div class="hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ----------------------------------------------------------------------------

st.sidebar.markdown("## 🎓 StudentHub")
st.sidebar.caption("Performance & Management")
st.sidebar.markdown("---")
st.sidebar.caption(f"Signed in as **{st.session_state.get('username', 'admin')}**")

page = st.sidebar.radio(
    "Navigation",
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

df_sidebar = cached_students()
st.sidebar.markdown("---")
st.sidebar.metric("Students", len(df_sidebar))
st.sidebar.caption("☁️ Persistent storage: Turso")

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()


# ----------------------------------------------------------------------------
# PAGE 1: DASHBOARD
# ----------------------------------------------------------------------------

if page == "Dashboard":
    page_header(
        "📊 Performance Dashboard",
        "A fast overview of academic performance and attendance.",
    )

    df = cached_students()

    if df.empty:
        st.info("No student data available. Add students from the sidebar.")
    else:
        total_students = len(df)
        avg_score = df["Score"].mean()
        avg_attendance = df["Attendance (%)"].mean()
        top_student = df.loc[df["Score"].idxmax(), "Name"]

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            metric_card("TOTAL STUDENTS", f"{total_students}", "Active records")
        with m2:
            metric_card("AVERAGE SCORE", f"{avg_score:.1f}", "Out of 100")
        with m3:
            metric_card("AVG ATTENDANCE", f"{avg_attendance:.1f}%", "Class average")
        with m4:
            metric_card("TOP PERFORMER", top_student, "Highest score")

        st.markdown("### 📈 Performance Overview")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            fig_bar = px.bar(
                df,
                x="Name",
                y="Score",
                text="Score",
                color="Grade",
                color_discrete_map={
                    "A": "#16a34a",
                    "B": "#2563eb",
                    "C": "#f59e0b",
                    "F": "#dc2626",
                },
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(
                height=390,
                yaxis_range=[0, 110],
                xaxis_title=None,
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig_bar,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        with chart_col2:
            fig_line = px.line(
                df,
                x="Name",
                y="Attendance (%)",
                markers=True,
            )
            fig_line.update_layout(
                height=390,
                yaxis_range=[0, 100],
                xaxis_title=None,
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig_line,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        st.markdown("### 🎯 Grade Distribution")

        grade_counts = (
            df["Grade"]
            .value_counts()
            .reindex(["A", "B", "C", "F"], fill_value=0)
            .reset_index()
        )
        grade_counts.columns = ["Grade", "Count"]

        pie_col, risk_col = st.columns([1, 1])

        with pie_col:
            fig_pie = px.pie(
                grade_counts,
                names="Grade",
                values="Count",
                hole=0.55,
                color="Grade",
                color_discrete_map={
                    "A": "#16a34a",
                    "B": "#2563eb",
                    "C": "#f59e0b",
                    "F": "#dc2626",
                },
            )
            fig_pie.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(
                fig_pie,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        with risk_col:
            st.markdown("#### ⚠️ Students Needing Attention")
            at_risk = df[(df["Score"] < 60) | (df["Attendance (%)"] < 75)].copy()

            if at_risk.empty:
                st.success("No students currently need attention.")
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
                        ["ID", "Name", "Score", "Attendance (%)", "Reason"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


# ----------------------------------------------------------------------------
# PAGE 2: STUDENT DIRECTORY
# ----------------------------------------------------------------------------

elif page == "Student Directory":
    page_header(
        "📋 Student Directory",
        "Search, filter and export student records.",
    )

    df = cached_students()

    search_col, grade_col = st.columns([2, 1])
    with search_col:
        search_term = st.text_input("🔍 Search by name or ID")
    with grade_col:
        grade_filter = st.multiselect(
            "Grade",
            options=["A", "B", "C", "F"],
        )

    filtered_df = df.copy()

    if search_term:
        filtered_df = filtered_df[
            filtered_df["Name"].str.contains(
                search_term, case=False, na=False
            )
            | filtered_df["ID"].astype(str).str.contains(search_term)
        ]

    if grade_filter:
        filtered_df = filtered_df[filtered_df["Grade"].isin(grade_filter)]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(f"Showing {len(filtered_df)} of {len(df)} students")

    st.download_button(
        "⬇️ Download CSV",
        data=convert_df_to_csv(filtered_df),
        file_name="student_directory.csv",
        mime="text/csv",
    )


# ----------------------------------------------------------------------------
# PAGE 3: STUDENT PROFILE
# ----------------------------------------------------------------------------

elif page == "Student Profile":
    page_header(
        "👨‍🎓 Student Profile",
        "Complete academic and attendance overview.",
    )

    df = cached_students()

    if df.empty:
        st.info("No students available.")
    else:
        selected_profile_id = st.selectbox(
            "Select Student",
            options=df["ID"].tolist(),
            format_func=lambda x: (
                f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
            ),
            key="profile_student_id",
        )

        student = df[df["ID"] == selected_profile_id].iloc[0]
        subjects_df = cached_subjects(selected_profile_id)
        attendance_df = cached_attendance(selected_profile_id)

        st.markdown(
            f"""
            <div class="profile-header">
                <h2 style="margin:0">{student["Name"]}</h2>
                <p style="margin:6px 0 0;color:#64748b">
                    Student ID: {student["ID"]} &nbsp;•&nbsp;
                    Grade: {student["Grade"]}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Overall Score", f'{student["Score"]}/100')
        with c2:
            st.metric("Attendance", f'{student["Attendance (%)"]}%')
        with c3:
            if student["Score"] >= 90:
                status = "Excellent"
            elif student["Score"] >= 70:
                status = "Good"
            elif student["Score"] >= 60:
                status = "Needs Improvement"
            else:
                status = "At Risk"
            st.metric("Performance", status)

        st.markdown("### 📚 Subject Performance")

        if subjects_df.empty:
            st.info("No subject scores recorded for this student.")
        else:
            fig = px.bar(
                subjects_df,
                x="subject_name",
                y="score",
                text="score",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=360,
                yaxis_range=[0, 110],
                xaxis_title=None,
                yaxis_title="Score",
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        st.markdown("### 🗓️ Attendance Trend")

        if attendance_df.empty:
            st.info("No attendance history recorded.")
        else:
            attendance_df = attendance_df.sort_values("log_date")
            fig_att = px.line(
                attendance_df,
                x="log_date",
                y="attendance_pct",
                markers=True,
            )
            fig_att.update_layout(
                height=330,
                yaxis_range=[0, 100],
                xaxis_title="Date",
                yaxis_title="Attendance (%)",
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig_att,
                use_container_width=True,
                config={"displayModeBar": False},
            )


# ----------------------------------------------------------------------------
# PAGE 4: ADD NEW STUDENT
# ----------------------------------------------------------------------------

elif page == "Add New Student":
    page_header(
        "➕ Add New Student",
        "Register a student and calculate the grade automatically.",
    )

    with st.form("add_student_form", clear_on_submit=True):
        c1, c2 = st.columns(2)

        with c1:
            new_id = st.number_input(
                "Student ID",
                min_value=1,
                step=1,
                format="%d",
            )
            new_name = st.text_input("Full Name")

        with c2:
            new_score = st.slider("Score", 0, 100, 75)
            new_attendance = st.slider("Attendance (%)", 0, 100, 85)

        submitted = st.form_submit_button(
            "➕ Add Student",
            use_container_width=True,
        )

        if submitted:
            if not new_name.strip():
                st.error("Please enter a valid student name.")
            elif student_id_exists(int(new_id)):
                st.error(f"Student ID {int(new_id)} already exists.")
            else:
                new_grade = calculate_grade(new_score)
                insert_student(
                    int(new_id),
                    new_name.strip(),
                    new_grade,
                    new_score,
                    new_attendance,
                )
                invalidate_data_cache()
                st.success(
                    f"{new_name} added successfully with grade {new_grade}."
                )
                st.rerun()


# ----------------------------------------------------------------------------
# PAGE 5: EDIT / DELETE STUDENT
# ----------------------------------------------------------------------------

elif page == "Edit / Delete Student":
    page_header(
        "✏️ Manage Student",
        "Update or remove an existing student record.",
    )

    df = cached_students()

    if df.empty:
        st.info("No students in the database.")
    else:
        selected_id = st.selectbox(
            "Select Student",
            options=df["ID"].tolist(),
            format_func=lambda x: (
                f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
            ),
        )

        student_row = df[df["ID"] == selected_id].iloc[0]

        with st.form("edit_student_form"):
            edit_name = st.text_input(
                "Full Name",
                value=student_row["Name"],
            )
            edit_score = st.slider(
                "Score",
                0,
                100,
                int(student_row["Score"]),
            )
            edit_attendance = st.slider(
                "Attendance (%)",
                0,
                100,
                int(student_row["Attendance (%)"]),
            )

            update_clicked = st.form_submit_button(
                "💾 Update Student",
                use_container_width=True,
            )

        if update_clicked:
            if not edit_name.strip():
                st.error("Name cannot be empty.")
            else:
                edit_grade = calculate_grade(edit_score)
                update_student(
                    int(selected_id),
                    edit_name.strip(),
                    edit_grade,
                    edit_score,
                    edit_attendance,
                )
                invalidate_data_cache()
                st.success("Student updated successfully.")
                st.rerun()

        st.markdown("---")

        if st.button("🗑️ Delete Student", use_container_width=True):
            delete_student(int(selected_id))
            invalidate_data_cache()
            st.success(f"Student {selected_id} deleted.")
            st.rerun()


# ----------------------------------------------------------------------------
# PAGE 6: SUBJECTS & CHARTS
# ----------------------------------------------------------------------------

elif page == "Subjects & Charts":
    page_header(
        "📚 Subjects & Performance",
        "Track subject-level scores and class averages.",
    )

    df = cached_students()

    if df.empty:
        st.info("Add a student first.")
    else:
        with st.form("add_subject_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                subj_student_id = st.selectbox(
                    "Student",
                    options=df["ID"].tolist(),
                    format_func=lambda x: (
                        f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
                    ),
                )

            with c2:
                subj_name = st.text_input("Subject Name")

            with c3:
                subj_score = st.slider("Subject Score", 0, 100, 75)

            submitted = st.form_submit_button(
                "➕ Add Subject Score",
                use_container_width=True,
            )

            if submitted:
                if not subj_name.strip():
                    st.error("Please enter a subject name.")
                else:
                    add_subject_score(
                        int(subj_student_id),
                        subj_name.strip(),
                        subj_score,
                    )
                    invalidate_data_cache()
                    st.success("Subject score added.")
                    st.rerun()

        st.markdown("---")

        chart_student_id = st.selectbox(
            "View student",
            options=df["ID"].tolist(),
            format_func=lambda x: (
                f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
            ),
            key="subject_chart_student",
        )

        subj_df = cached_subjects(chart_student_id)

        if subj_df.empty:
            st.info("No subject scores recorded.")
        else:
            fig = px.bar(
                subj_df,
                x="subject_name",
                y="score",
                text="score",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=380,
                yaxis_range=[0, 110],
                xaxis_title="Subject",
                yaxis_title="Score",
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

            st.dataframe(
                subj_df[["subject_name", "score"]].rename(
                    columns={
                        "subject_name": "Subject",
                        "score": "Score",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        all_subj_df = cached_subjects()

        if not all_subj_df.empty:
            st.markdown("### 🏫 Class Average by Subject")
            avg_by_subject = (
                all_subj_df.groupby("subject_name")["score"]
                .mean()
                .reset_index()
            )
            avg_by_subject.columns = ["Subject", "Average Score"]

            fig2 = px.bar(
                avg_by_subject,
                x="Subject",
                y="Average Score",
                text="Average Score",
            )
            fig2.update_traces(
                texttemplate="%{text:.1f}",
                textposition="outside",
            )
            fig2.update_layout(
                height=350,
                yaxis_range=[0, 110],
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig2,
                use_container_width=True,
                config={"displayModeBar": False},
            )


# ----------------------------------------------------------------------------
# PAGE 7: ATTENDANCE HISTORY
# ----------------------------------------------------------------------------

elif page == "Attendance History":
    page_header(
        "🗓️ Attendance History",
        "Record attendance and monitor trends over time.",
    )

    df = cached_students()

    if df.empty:
        st.info("Add a student first.")
    else:
        with st.form("add_attendance_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                att_student_id = st.selectbox(
                    "Student",
                    options=df["ID"].tolist(),
                    format_func=lambda x: (
                        f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
                    ),
                )

            with c2:
                att_date = st.date_input("Date", value=date.today())

            with c3:
                att_pct = st.slider("Attendance (%)", 0, 100, 90)

            submitted = st.form_submit_button(
                "➕ Add Attendance Record",
                use_container_width=True,
            )

            if submitted:
                add_attendance_record(
                    int(att_student_id),
                    att_date.isoformat(),
                    att_pct,
                )
                invalidate_data_cache()
                st.success("Attendance record added.")
                st.rerun()

        st.markdown("---")

        trend_student_id = st.selectbox(
            "View student attendance",
            options=df["ID"].tolist(),
            format_func=lambda x: (
                f"{x} — {df.loc[df['ID'] == x, 'Name'].values[0]}"
            ),
            key="attendance_chart_student",
        )

        att_df = cached_attendance(trend_student_id)

        if att_df.empty:
            st.info("No attendance history recorded.")
        else:
            att_df = att_df.sort_values("log_date")
            fig = px.line(
                att_df,
                x="log_date",
                y="attendance_pct",
                markers=True,
            )
            fig.update_layout(
                height=360,
                yaxis_range=[0, 100],
                xaxis_title="Date",
                yaxis_title="Attendance (%)",
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

            st.dataframe(
                att_df[["log_date", "attendance_pct"]].rename(
                    columns={
                        "log_date": "Date",
                        "attendance_pct": "Attendance (%)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )


# ----------------------------------------------------------------------------
# PAGE 8: BULK IMPORT (CSV)
# ----------------------------------------------------------------------------

elif page == "Bulk Import (CSV)":
    page_header(
        "📥 Bulk Import",
        "Import multiple student records from a CSV file.",
    )

    template_df = pd.DataFrame(
        {
            "ID": [201, 202],
            "Name": ["Sample Student A", "Sample Student B"],
            "Score": [88, 72],
            "Attendance": [90, 76],
        }
    )

    st.download_button(
        "⬇️ Download CSV Template",
        data=convert_df_to_csv(template_df),
        file_name="student_import_template.csv",
        mime="text/csv",
    )

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
    )

    if uploaded_file is not None:
        try:
            import_df = pd.read_csv(uploaded_file)
            required_cols = {"ID", "Name", "Score", "Attendance"}

            if not required_cols.issubset(set(import_df.columns)):
                st.error(
                    "CSV must contain: ID, Name, Score, Attendance"
                )
            else:
                st.dataframe(
                    import_df,
                    use_container_width=True,
                    hide_index=True,
                )

                if st.button(
                    "✅ Confirm and Import",
                    use_container_width=True,
                ):
                    added, skipped = 0, 0

                    for _, row in import_df.iterrows():
                        sid = int(row["ID"])
                        name = str(row["Name"]).strip()
                        score = int(row["Score"])
                        attendance = int(row["Attendance"])

                        if (
                            not name
                            or student_id_exists(sid)
                            or not 0 <= score <= 100
                            or not 0 <= attendance <= 100
                        ):
                            skipped += 1
                            continue

                        grade = calculate_grade(score)
                        insert_student(
                            sid,
                            name,
                            grade,
                            score,
                            attendance,
                        )
                        added += 1

                    invalidate_data_cache()
                    st.success(
                        f"Import complete: {added} added, {skipped} skipped."
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Could not process file: {e}")

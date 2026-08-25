# --------------------------------------------------------------
# StudentHub OS – Advanced Streamlit Application
# --------------------------------------------------------------
# Author: Inception Labs (Mercury)
# --------------------------------------------------------------

import os
import time
import hmac
import html
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import streamlit as st
import libsql
from groq import Groq
from sklearn.linear_model import LinearRegression
import numpy as np

# --------------------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------------------
st.set_page_config(
    page_title="StudentHub OS – Advanced",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/inceptionlabs/studenthub",
        "Report a bug": "https://github.com/inceptionlabs/studenthub/issues",
    },
)

# --------------------------------------------------------------
# GLOBAL STYLE (Tailwind‑like via custom CSS)
# --------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ==== Base ==== */
    .stApp { font-family: 'Inter', sans-serif; background:#f8fafc; }
    .sidebar .stSelectbox div { color:#f8fafc; }
    .sidebar .stSelectbox label { color:#cbd5e1; }

    /* ==== Hero ==== */
    .hero {
        background:linear-gradient(135deg,#1e293b,#334155);
        color:#fff; padding:2rem 3rem; border-radius:1rem;
        box-shadow:0 4px 20px rgba(15,23,42,.08);
    }
    .hero h1 { font-size:2rem; font-weight:700; margin:0; }
    .hero p { margin-top:.5rem; color:#94a3b8; }

    /* ==== Cards ==== */
    .card {
        background:#fff; border-radius:.75rem; padding:1.5rem;
        box-shadow:0 2px 6px rgba(0,0,0,.05);
        transition:transform .2s,box-shadow .2s;
    }
    .card:hover { transform:translateY(-4px); box-shadow:0 8px 12px rgba(0,0,0,.1); }
    .card-title { font-weight:600; color:#0f172a; }
    .card-value { font-size:1.75rem; font-weight:800; margin-top:.25rem; }

    /* ==== Tables ==== */
    .dataframe { border-radius:.5rem; overflow:hidden; }

    /* ==== Login ==== */
    .login-wrapper { display:flex; justify-content:center; align-items:center; min-height:85vh; }
    .login-card {
        background:rgba(30,41,59,.55); backdrop-filter:blur(20px);
        border-radius:1.5rem; padding:2.5rem 2rem; width:100%; max-width:420px;
        box-shadow:0 20px 60px rgba(0,0,0,.4);
    }
    .login-badge { background:linear-gradient(135deg,#ff4b4b,#ff7a59);
        width:64px;height:64px;border-radius:14px;display:flex;align-items:center;justify-content:center;
        font-size:30px;color:#fff;margin:auto;margin-bottom:1rem;
    }
    .login-title { font-size:1.6rem;font-weight:800;color:#f8fafc;text-align:center; }
    .login-subtitle { font-size:.9rem;color:#94a3b8;text-align:center;margin-bottom:1.5rem; }
    .login-btn { background:linear-gradient(135deg,#ff4b4b,#ff6b57);color:#fff;
        border:none;border-radius:.75rem;padding:.75rem 1rem;font-weight:700;cursor:pointer;
        width:100%;margin-top:.5rem;box-shadow:0 8px 20px rgba(255,75,75,.25); }
    .login-btn:hover { transform:translateY(-2px);box-shadow:0 10px 26px rgba(255,75,75,.35); }

    /* ==== Misc ==== */
    .toast { position:fixed;bottom:2rem;right:2rem;background:#10b981;color:#fff;
        padding:.75rem 1rem;border-radius:.5rem;box-shadow:0 4px 12px rgba(0,0,0,.1); }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------
# SECRET / ENV HELPERS
# --------------------------------------------------------------
def _secret(name: str, default=None):
    """Read a secret from Streamlit or environment."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    if value:
        return value
    return os.getenv(name, default)

TURSO_DATABASE_URL = _secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _secret("TURSO_AUTH_TOKEN")
GROQ_API_KEY = _secret("GROQ_API_KEY")
GROQ_MODEL = _secret("GROQ_MODEL", "openai/gpt-oss-120b")
ADMIN_USERNAME = _secret("ADMIN_USERNAME")
ADMIN_PASSWORD = _secret("ADMIN_PASSWORD")

# --------------------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60
SESSION_TIMEOUT = 30 * 60  # 30 min

if "auth" not in st.session_state:
    st.session_state.auth = {
        "logged_in": False,
        "attempts": 0,
        "lockout_until": 0,
        "last_active": time.time(),
    }

def _check_login(user, pwd):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return False
    return (
        hmac.compare_digest(user, ADMIN_USERNAME)
        and hmac.compare_digest(pwd, ADMIN_PASSWORD)
    )

# --------------------------------------------------------------
# DATABASE LAYER
# --------------------------------------------------------------
@st.cache_resource
def get_conn():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        st.error("Missing Turso credentials.")
        st.stop()
    return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)

def _df_from_cursor(cur, cols):
    return pd.DataFrame(cur.fetchall(), columns=cols)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
            attendance INTEGER NOT NULL CHECK(attendance BETWEEN 0 AND 100),
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_name TEXT NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            attendance_pct INTEGER NOT NULL CHECK(attendance_pct BETWEEN 0 AND 100),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_subjects_student ON subjects(student_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_log(student_id);
        """
    )
    conn.commit()

@st.cache_data(ttl=60)
def fetch_students():
    cur = get_conn().cursor()
    cur.execute(
        """
        SELECT id AS ID, name AS Name, grade AS Grade,
               score AS Score, attendance AS "Attendance (%)"
        FROM students ORDER BY id
        """
    )
    return _df_from_cursor(cur, ["ID", "Name", "Grade", "Score", "Attendance (%)"])

@st.cache_data(ttl=60)
def fetch_subjects(student_id=None):
    cur = get_conn().cursor()
    base = """
        SELECT s.id, s.student_id, st.name AS student_name,
               s.subject_name, s.score
        FROM subjects s JOIN students st ON s.student_id = st.id
        """
    if student_id:
        cur.execute(base + "WHERE s.student_id = ? ORDER BY s.subject_name", (student_id,))
    else:
        cur.execute(base + "ORDER BY st.name, s.subject_name")
    return _df_from_cursor(cur, ["id", "student_id", "student_name", "subject_name", "score"])

@st.cache_data(ttl=60)
def fetch_attendance(student_id=None):
    cur = get_conn().cursor()
    base = """
        SELECT a.id, a.student_id, st.name AS student_name,
               a.log_date, a.attendance_pct
        FROM attendance_log a JOIN students st ON a.student_id = st.id
        """
    if student_id:
        cur.execute(base + "WHERE a.student_id = ? ORDER BY a.log_date", (student_id,))
    else:
        cur.execute(base + "ORDER BY st.name, a.log_date")
    return _df_from_cursor(cur, ["id", "student_id", "student_name", "log_date", "attendance_pct"])

def _invalidate_caches():
    fetch_students.clear()
    fetch_subjects.clear()
    fetch_attendance.clear()

def _execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    _invalidate_caches()

def _student_exists(sid):
    cur = get_conn().cursor()
    cur.execute("SELECT 1 FROM students WHERE id=? LIMIT 1", (sid,))
    return cur.fetchone() is not None

# --------------------------------------------------------------
# UTILITIES
# --------------------------------------------------------------
def grade_from_score(score):
    return "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "F"

def _to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# --------------------------------------------------------------
# INITIALIZE DB
# --------------------------------------------------------------
init_db()

# --------------------------------------------------------------
# AUTH FLOW
# --------------------------------------------------------------
auth = st.session_state.auth
now = time.time()
if auth["logged_in"] and now - auth["last_active"] > SESSION_TIMEOUT:
    auth["logged_in"] = False
    st.warning("Session timed out – please log in again.")
    st.rerun()

if not auth["logged_in"]:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        st.error("Admin credentials not configured in secrets.")
        st.stop()

    locked = now < auth["lockout_until"]
    with st.container():
        st.markdown(
            """
            <div class="login-wrapper">
                <div class="login-card">
                    <div class="login-badge">🎓</div>
                    <div class="login-title">StudentHub OS</div>
                    <div class="login-subtitle">Admin Login</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if locked:
            remaining = int(auth["lockout_until"] - now)
            st.warning(f"Too many attempts – try again in {remaining}s.")
        with st.form("login_form", clear_on_submit=True):
            u = st.text_input("Username", disabled=locked)
            p = st.text_input("Password", type="password", disabled=locked)
            submitted = st.form_submit_button("Sign In")
            if submitted and not locked:
                if _check_login(u, p):
                    auth.update({"logged_in": True, "attempts": 0, "last_active": time.time()})
                    st.success("✅ Logged in")
                    st.rerun()
                else:
                    auth["attempts"] += 1
                    if auth["attempts"] >= MAX_LOGIN_ATTEMPTS:
                        auth["lockout_until"] = time.time() + LOCKOUT_SECONDS
                        auth["attempts"] = 0
                        st.error("🔒 Locked out – try later.")
                    else:
                        st.error(f"❌ Invalid – {MAX_LOGIN_ATTEMPTS - auth['attempts']} attempts left.")
        st.stop()

# --------------------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------------------
st.sidebar.title("📚 StudentHub OS")
st.sidebar.caption(f"Logged in as **{ADMIN_USERNAME}**")
st.sidebar.markdown("---")
pages = {
    "🏠 Dashboard": "dashboard",
    "👥 Directory": "directory",
    "🧭 Academics": "academics",
    "⚙️ Data Management": "manage",
    "🤖 AI Assistant": "ai",
}
choice = st.sidebar.radio("Navigate", list(pages.keys()))
st.sidebar.markdown("---")
st.sidebar.metric("Students", len(fetch_students()))
if st.sidebar.button("🚪 Logout"):
    auth["logged_in"] = False
    st.rerun()

# --------------------------------------------------------------
# PAGE: DASHBOARD
# --------------------------------------------------------------
if pages[choice] == "dashboard":
    st.markdown(
        """
        <div class="hero">
            <h1>Performance Dashboard</h1>
            <p>Quick overview of scores, attendance and trends.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    df = fetch_students()
    if df.empty:
        st.info("No data yet – add students via **Data Management**.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Students", len(df))
        col2.metric("Avg Score", f"{df['Score'].mean():.1f}")
        col3.metric("Avg Attendance", f"{df['Attendance (%)'].mean():.1f}%")
        top = df.loc[df["Score"].idxmax(), "Name"]
        col4.metric("Top Performer", top)

        # Scores by student
        st.subheader("Scores by Student")
        fig_score = px.bar(
            df,
            x="Name",
            y="Score",
            color="Grade",
            color_discrete_map={"A": "#10b981", "B": "#3b82f6", "C": "#f59e0b", "F": "#ef4444"},
        )
        fig_score.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_score, use_container_width=True)

        # Grade distribution
        st.subheader("Grade Distribution")
        grade_counts = df["Grade"].value_counts().reset_index()
        grade_counts.columns = ["Grade", "Count"]
        fig_grade = px.pie(
            grade_counts,
            names="Grade",
            values="Count",
            hole=0.6,
            color="Grade",
            color_discrete_map={"A": "#10b981", "B": "#3b82f6", "C": "#f59e0b", "F": "#ef4444"},
        )
        fig_grade.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_grade, use_container_width=True)

# --------------------------------------------------------------
# PAGE: DIRECTORY
# --------------------------------------------------------------
elif pages[choice] == "directory":
    st.markdown(
        """
        <div class="hero">
            <h1>Student Directory</h1>
            <p>Search, filter and explore individual profiles.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    df = fetch_students()
    if df.empty:
        st.info("No records – add students first.")
    else:
        tab_grid, tab_profile = st.tabs(["📋 Grid", "👤 Profile"])
        with tab_grid:
            search = st.text_input("Search (Name or ID)", placeholder="e.g. Jane")
            grade_filter = st.multiselect("Filter Grade", options=["A", "B", "C", "F"])
            filtered = df.copy()
            if search:
                filtered = filtered[
                    filtered["Name"].str.contains(search, case=False, regex=False)
                    | filtered["ID"].astype(str).str.contains(search, regex=False)
                ]
            if grade_filter:
                filtered = filtered[filtered["Grade"].isin(grade_filter)]
            st.dataframe(filtered, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export CSV",
                data=_to_csv(filtered),
                file_name="students_directory.csv",
                mime="text/csv",
            )
        with tab_profile:
            sid = st.selectbox(
                "Select Student",
                options=df["ID"],
                format_func=lambda x: f"{x} – {df.loc[df['ID']==x, 'Name'].values[0]}",
            )
            student = df[df["ID"] == sid].iloc[0]
            st.subheader(f"Profile: {student['Name']}")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Score", f"{student['Score']}/100")
            col_b.metric("Attendance", f"{student['Attendance (%)']}%")
            col_c.metric("Grade", student["Grade"])
            subjects = fetch_subjects(sid)
            if not subjects.empty:
                fig = px.bar(subjects, x="subject_name", y="score", text="score")
                fig.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No subject records for this student.")

# --------------------------------------------------------------
# PAGE: ACADEMICS
# --------------------------------------------------------------
elif pages[choice] == "academics":
    st.markdown(
        """
        <div class="hero">
            <h1>Academics & Attendance</h1>
            <p>Log scores, attendance and view trends.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    df = fetch_students()
    if df.empty:
        st.warning("Add students before logging data.")
    else:
        tab_subjects, tab_attendance = st.tabs(["📚 Subject Scores", "🗓️ Attendance Log"])
        with tab_subjects:
            with st.form("subj_form", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 3, 2])
                sid = c1.selectbox("Student", options=df["ID"], format_func=lambda x: f"{x} – {df.loc[df['ID']==x, 'Name'].values[0]}")
                subj = c2.text_input("Subject Name")
                score = c3.slider("Score", 0, 100, 75)
                if st.form_submit_button("Add"):
                    if not subj:
                        st.error("Subject name required.")
                    else:
                        _execute("INSERT INTO subjects (student_id, subject_name, score) VALUES (?,?,?)", (sid, subj, score))
                        st.success("✅ Subject score added.")
                        st.rerun()
        with tab_attendance:
            with st.form("att_form", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 3, 2])
                sid = c1.selectbox("Student", options=df["ID"], format_func=lambda x: f"{x} – {df.loc[df['ID']==x, 'Name'].values[0]}")
                att_date = c2.date_input("Date", value=date.today())
                pct = c3.slider("Attendance %", 0, 100, 100)
                if st.form_submit_button("Log"):
                    _execute("INSERT INTO attendance_log (student_id, log_date, attendance_pct) VALUES (?,?,?)", (sid, att_date.isoformat(), pct))
                    st.success("✅ Attendance logged.")
                    st.rerun()

# --------------------------------------------------------------
# PAGE: DATA MANAGEMENT
# --------------------------------------------------------------
elif pages[choice] == "manage":
    st.markdown(
        """
        <div class="hero">
            <h1>Data Management</h1>
            <p>Add, edit, delete or bulk‑import student records.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tab_add, tab_edit, tab_bulk = st.tabs(["➕ Add", "✏️ Edit/Delete", "📥 Bulk Import"])

    # ----- Add New -----
    with tab_add:
        with st.form("add_student", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sid = c1.number_input("Student ID", min_value=1, step=1)
            name = c2.text_input("Full Name")
            score = c1.slider("Score", 0, 100, 75)
            attendance = c2.slider("Attendance %", 0, 100, 85)
            if st.form_submit_button("Add Student"):
                if not name:
                    st.error("Name required.")
                elif _student_exists(sid):
                    st.error("ID already exists.")
                else:
                    _execute(
                        "INSERT INTO students (id, name, grade, score, attendance, created_at) VALUES (?,?,?,?,?,?)",
                        (sid, name.strip(), grade_from_score(score), score, attendance, datetime.now().isoformat()),
                    )
                    st.success("✅ Student added.")
                    st.rerun()

    # ----- Edit / Delete -----
    with tab_edit:
        df = fetch_students()
        if df.empty:
            st.info("No students to edit.")
        else:
            sid = st.selectbox("Select Student", options=df["ID"], format_func=lambda x: f"{x} – {df.loc[df['ID']==x, 'Name'].values[0]}")
            rec = df[df["ID"] == sid].iloc[0]
            with st.form("edit_form"):
                new_name = st.text_input("Name", value=rec["Name"])
                new_score = st.slider("Score", 0, 100, int(rec["Score"]))
                new_att = st.slider("Attendance %", 0, 100, int(rec["Attendance (%)"]))
                if st.form_submit_button("💾 Save"):
                    _execute(
                        "UPDATE students SET name=?, grade=?, score=?, attendance=? WHERE id=?",
                        (new_name.strip(), grade_from_score(new_score), new_score, new_att, sid),
                    )
                    st.success("✅ Updated.")
                    st.rerun()
            st.markdown("---")
            confirm = st.checkbox(f"Delete **{rec['Name']}** permanently")
            if st.button("🗑️ Delete", disabled=not confirm, type="primary"):
                _execute("DELETE FROM students WHERE id=?", (sid,))
                st.success("🗑️ Student removed.")
                st.rerun()

    # ----- Bulk Import -----
    with tab_bulk:
        st.info("Upload a CSV with columns: **ID, Name, Score, Attendance**")
        csv = st.file_uploader("CSV file", type=["csv"])
        if csv:
            try:
                bulk_df = pd.read_csv(csv)
                required = {"ID", "Name", "Score", "Attendance"}
                if not required.issubset(bulk_df.columns):
                    st.error(f"Missing columns: {required - set(bulk_df.columns)}")
                else:
                    st.dataframe(bulk_df.head(5), hide_index=True)
                    if st.button("Import"):
                        added, skipped, errors = 0, 0, []
                        for _, row in bulk_df.iterrows():
                            try:
                                sid = int(row["ID"])
                                name = str(row["Name"]).strip()
                                score = int(row["Score"])
                                att = int(row["Attendance"])
                                if not name or _student_exists(sid):
                                    skipped += 1
                                    continue
                                if not (0 <= score <= 100 and 0 <= att <= 100):
                                    errors.append(f"Row {_}: out‑of‑range values")
                                    continue
                                _execute(
                                    "INSERT INTO students (id, name, grade, score, attendance, created_at) VALUES (?,?,?,?,?,?)",
                                    (sid, name, grade_from_score(score), score, att, datetime.now().isoformat()),
                                )
                                added += 1
                            except Exception as e:
                                errors.append(str(e))
                        st.success(f"✅ Added {added}, skipped {skipped}.")
                        if errors:
                            st.warning("⚠️ Errors:")
                            for e in errors[:5]:
                                st.text(f"• {e}")
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")

# --------------------------------------------------------------
# PAGE: AI ASSISTANT
# --------------------------------------------------------------
elif pages[choice] == "ai":
    st.markdown(
        """
        <div class="hero">
            <h1>AI Data Assistant</h1>
            <p>Ask natural‑language questions about your student data.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not GROQ_API_KEY:
        st.warning("Groq API key missing – add it to secrets to enable AI.")
    else:
        if "chat" not in st.session_state:
            st.session_state.chat = [
                {"role": "assistant", "content": "Hello! 👋 Ask me anything about the student data."}
            ]

        # Render chat history
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # Input form
        with st.form("ai_form", clear_on_submit=True):
            user_q = st.text_input("Your question", placeholder="e.g. Who needs extra tutoring?")
            send = st.form_submit_button("Ask")

        if send and user_q:
            st.session_state.chat.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.write(user_q)

            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    try:
                        # Gather data snapshots
                        students = fetch_students()
                        subjects = fetch_subjects()
                        attendance = fetch_attendance()
                        context = (
                            "STUDENTS:\n" + students.to_string(index=False) + "\n\n"
                            "SUBJECTS:\n" + subjects.to_string(index=False) + "\n\n"
                            "ATTENDANCE:\n" + attendance.to_string(index=False)
                        )
                        system_prompt = """
You are a concise, data‑driven assistant for a student management system.
Never fabricate data. Use the provided tables as the sole source of truth.
Answer in plain English, include numbers where relevant, and keep responses under 150 words.
"""
                        client = Groq(api_key=GROQ_API_KEY)
                        resp = client.chat.completions.create(
                            model=GROQ_MODEL,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"{context}\n\nQuestion: {user_q}"},
                            ],
                        )
                        answer = resp.choices[0].message.content if resp.choices else "I couldn't generate a response."
                        st.write(answer)
                        st.session_state.chat.append({"role": "assistant", "content": answer})
                        st.rerun()
                    except Exception as e:
                        st.error("AI error")
                        st.code(str(e), language="text")

        if len(st.session_state.chat) > 1:
            if st.button("🗑️ Clear chat"):
                st.session_state.chat = [{"role": "assistant", "content": "Hello! 👋 Ask me anything about the student data."}]
                st.rerun()

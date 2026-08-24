import streamlit as st
import pandas as pd
import hmac
import os
import plotly.express as px
from datetime import datetime, date
import libsql
from google import genai

# ----------------------------------------------------------------------------
# PAGE CONFIGURATION
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="StudentHub OS",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------------
# SECRETS & AUTH CONFIG
# ----------------------------------------------------------------------------
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
GEMINI_API_KEY = _secret("GEMINI_API_KEY")
GEMINI_MODEL = _secret("GEMINI_MODEL", "gemini-3.6-flash")

def check_login(username: str, password: str) -> bool:
    configured_username = str(_secret("ADMIN_USERNAME", "admin"))
    configured_password = str(_secret("ADMIN_PASSWORD", "admin123")) # Fallback for local testing
    
    if not configured_password:
        return False
    return (
        hmac.compare_digest(username, configured_username)
        and hmac.compare_digest(password, configured_password)
    )

# ----------------------------------------------------------------------------
# MODERN UI/CSS INJECTION
# ----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Global App Styling */
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    
    /* Hero/Header Section */
    .hero {
        padding: 24px 32px;
        border-radius: 16px;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08);
    }
    .hero h1 { margin: 0; font-size: 1.8rem; font-weight: 700; letter-spacing: -0.5px; }
    .hero p { margin: 8px 0 0; color: #94a3b8; font-size: 1rem; }

    /* Custom Metric Cards */
    .metric-card {
        padding: 20px;
        border-radius: 16px;
        background: white;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 2rem; font-weight: 800; color: #0f172a; margin: 8px 0; }
    .metric-note { font-size: 0.8rem; color: #10b981; font-weight: 500; }

    /* Clean up native Streamlit elements */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding-top: 10px; padding-bottom: 10px; }
    div[data-testid="stMetric"] {
        background: white; border: 1px solid #e2e8f0; padding: 16px; 
        border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    
    /* Sidebar dark cards */
    [data-testid="stSidebar"] div[data-testid="stMetric"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        padding: 18px !important;
        border-radius: 16px !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
        min-height: 46px;
        background: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: #334155 !important;
        border-color: #475569 !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: #1e293b !important;
    }

    /* Mobile UI */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        .hero {
            padding: 18px !important;
            border-radius: 14px !important;
        }

        .hero h1 {
            font-size: 1.4rem !important;
        }

        .hero p {
            font-size: 0.9rem !important;
        }

        div[data-testid="stTextInput"] input {
            font-size: 16px !important;
            min-height: 48px !important;
            border-radius: 12px !important;
        }

        div.stButton > button {
            min-height: 48px !important;
            border-radius: 12px !important;
            font-size: 15px !important;
        }

        [data-testid="stChatMessage"] {
            padding: 8px 4px !important;
        }
    }


    /* Premium AI assistant */
    .ai-section-title {
        display:flex; align-items:center; gap:14px; margin:12px 0 18px;
    }
    .ai-title-icon {
        width:48px; height:48px; border-radius:14px;
        display:flex; align-items:center; justify-content:center;
        background:linear-gradient(135deg,#ff4b4b,#ff7a59);
        color:white; font-size:23px; font-weight:800;
        box-shadow:0 8px 22px rgba(255,75,75,.20);
    }
    .ai-title { font-size:1.75rem; font-weight:800; color:#0f172a; }
    .ai-subtitle { margin-top:4px; color:#64748b; font-size:.92rem; }

    div[data-testid="stForm"] {
        background:#fff; border:1px solid #e2e8f0 !important;
        border-radius:18px !important; padding:10px !important;
        box-shadow:0 8px 30px rgba(15,23,42,.07);
    }
    div[data-testid="stForm"] input {
        min-height:50px !important; background:#f8fafc !important;
        color:#0f172a !important; border:1px solid #e2e8f0 !important;
        border-radius:12px !important; font-size:15px !important;
    }
    div[data-testid="stForm"] input:focus {
        border-color:#ff4b4b !important;
        box-shadow:0 0 0 3px rgba(255,75,75,.10) !important;
    }
    div[data-testid="stForm"] button[kind="formSubmit"] {
        min-height:50px !important; border-radius:12px !important;
        border:none !important; background:linear-gradient(135deg,#ff4b4b,#ff6b57) !important;
        color:white !important; font-weight:700 !important; font-size:15px !important;
        box-shadow:0 6px 16px rgba(255,75,75,.20);
    }
    [data-testid="stChatMessage"] {
        border-radius:16px !important; padding:14px 16px !important;
        margin:10px 0 !important; border:1px solid #e8edf3 !important;
    }
    [data-testid="stChatMessage"] p { font-size:15px !important; line-height:1.65 !important; }

    /* Premium sidebar */
    [data-testid="stSidebar"] {
        background:linear-gradient(180deg,#0b1220 0%,#111827 100%) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stMetric"] {
        background:linear-gradient(145deg,#1b2940,#172236) !important;
        border:1px solid #334155 !important; border-radius:17px !important;
        box-shadow:0 10px 28px rgba(0,0,0,.18) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] { color:#cbd5e1 !important; }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] { color:#fff !important; }
    [data-testid="stSidebar"] .stButton > button {
        background:#172236 !important; color:#e2e8f0 !important;
        border:1px solid #334155 !important; border-radius:12px !important;
        min-height:44px !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background:#24324a !important; border-color:#475569 !important;
    }

    @media (max-width:768px) {
        .block-container { padding:1rem !important; }
        .ai-title { font-size:1.45rem; }
        .ai-title-icon { width:42px; height:42px; border-radius:12px; }
        .ai-subtitle { font-size:.82rem; }
        div[data-testid="stForm"] { padding:8px !important; border-radius:14px !important; }
        div[data-testid="stForm"] input,
        div[data-testid="stForm"] button[kind="formSubmit"] { min-height:48px !important; }
        [data-testid="stChatMessage"] { padding:10px 12px !important; margin:8px 0 !important; }
    }

</style>
""", unsafe_allow_html=True)

def page_header(title, subtitle):
    st.markdown(f"""
        <div class="hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

def metric_card(label, value, note=""):
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# DATABASE LAYER
# ----------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        st.error("⚠️ Database missing! Configure TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.")
        st.stop()
    return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)

def _rows_to_dataframe(cursor, columns):
    return pd.DataFrame(cursor.fetchall(), columns=columns)

def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Create Tables
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, grade TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                attendance INTEGER NOT NULL CHECK(attendance >= 0 AND attendance <= 100),
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
                subject_name TEXT NOT NULL, score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS attendance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
                log_date TEXT NOT NULL, attendance_pct INTEGER NOT NULL CHECK(attendance_pct >= 0 AND attendance_pct <= 100),
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_subjects_student_id ON subjects(student_id);
            CREATE INDEX IF NOT EXISTS idx_attendance_student_id ON attendance_log(student_id);
        """)
        conn.commit()
    except Exception as e:
        st.error(f"Database Initialization Error: {e}")

# ----------------------------------------------------------------------------
# CACHED DATA FETCHERS
# ----------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_students():
    cur = get_connection().cursor()
    cur.execute("SELECT id AS ID, name AS Name, grade AS Grade, score AS Score, attendance AS 'Attendance (%)' FROM students ORDER BY id ASC")
    return _rows_to_dataframe(cur, ["ID", "Name", "Grade", "Score", "Attendance (%)"])

@st.cache_data(ttl=60, show_spinner=False)
def fetch_subjects(student_id=None):
    cur = get_connection().cursor()
    query = "SELECT s.id, s.student_id, st.name AS student_name, s.subject_name, s.score FROM subjects s JOIN students st ON s.student_id = st.id "
    if student_id:
        cur.execute(query + "WHERE s.student_id = ? ORDER BY s.subject_name", (student_id,))
    else:
        cur.execute(query + "ORDER BY st.name, s.subject_name")
    return _rows_to_dataframe(cur, ["id", "student_id", "student_name", "subject_name", "score"])

@st.cache_data(ttl=60, show_spinner=False)
def fetch_attendance_log(student_id=None):
    cur = get_connection().cursor()
    query = "SELECT a.id, a.student_id, st.name AS student_name, a.log_date, a.attendance_pct FROM attendance_log a JOIN students st ON a.student_id = st.id "
    if student_id:
        cur.execute(query + "WHERE a.student_id = ? ORDER BY a.log_date", (student_id,))
    else:
        cur.execute(query + "ORDER BY st.name, a.log_date")
    return _rows_to_dataframe(cur, ["id", "student_id", "student_name", "log_date", "attendance_pct"])

def invalidate_data_cache():
    fetch_all_students.clear()
    fetch_subjects.clear()
    fetch_attendance_log.clear()

# ----------------------------------------------------------------------------
# CRUD HELPERS
# ----------------------------------------------------------------------------
def calculate_grade(score: int) -> str:
    if score >= 90: return "A"
    elif score >= 80: return "B"
    elif score >= 70: return "C"
    else: return "F"

def execute_write(query, params=()):
    conn = get_connection()
    conn.cursor().execute(query, params)
    conn.commit()
    invalidate_data_cache()

def student_id_exists(student_id) -> bool:
    cur = get_connection().cursor()
    cur.execute("SELECT 1 FROM students WHERE id=? LIMIT 1", (student_id,))
    return cur.fetchone() is not None

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# ----------------------------------------------------------------------------
# INITIALIZATION & AUTHENTICATION
# ----------------------------------------------------------------------------
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<center><h1>🎓 StudentHub OS</h1><p style='color:#64748b'>Secure Admin Portal</p></center>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            if st.form_submit_button("Authenticate", use_container_width=True):
                if check_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials.")
    st.stop()

# ----------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ----------------------------------------------------------------------------
st.sidebar.markdown("### 🎓 StudentHub OS")
st.sidebar.caption(f"Signed in as **{st.session_state.username}**")
st.sidebar.markdown("---")

nav_options = {
    "📊 Dashboard": "Overview & Metrics",
    "👩‍🎓 Directory & Profiles": "Search & View Students",
    "📚 Academics & Attendance": "Manage Subjects & Logs",
    "⚙️ Manage Data": "Add, Edit, Bulk Import",
    "🤖 AI Insights": "Data Assistant"
}

selection = st.sidebar.radio("Navigation", list(nav_options.keys()), format_func=lambda x: x)

df_all = fetch_all_students()
st.sidebar.markdown("---")
st.sidebar.metric("Total Enrolled", len(df_all))

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# ----------------------------------------------------------------------------
# VIEWS / PAGES
# ----------------------------------------------------------------------------

if selection == "📊 Dashboard":
    page_header("Performance Dashboard", "High-level overview of academic performance and attendance.")
    
    if df_all.empty:
        st.info("👋 Welcome! Navigate to 'Manage Data' to add your first student.")
    else:
        # Top Metrics
        total = len(df_all)
        avg_score = df_all["Score"].mean()
        avg_att = df_all["Attendance (%)"].mean()
        top_name = df_all.loc[df_all["Score"].idxmax(), "Name"]
        
        m1, m2, m3, m4 = st.columns(4)
        with m1: metric_card("Total Students", f"{total}", "Active Records")
        with m2: metric_card("Avg Score", f"{avg_score:.1f}", "Class Average")
        with m3: metric_card("Avg Attendance", f"{avg_att:.1f}%", "Overall")
        with m4: metric_card("Top Performer", top_name, "Highest Score")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📈 Scores by Student")
            fig1 = px.bar(df_all, x="Name", y="Score", color="Grade", 
                          color_discrete_map={"A":"#10b981", "B":"#3b82f6", "C":"#f59e0b", "F":"#ef4444"})
            fig1.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

        with c2:
            st.markdown("#### 🎯 Grade Distribution")
            grade_counts = df_all["Grade"].value_counts().reset_index()
            grade_counts.columns = ["Grade", "Count"]
            fig2 = px.pie(grade_counts, names="Grade", values="Count", hole=0.6,
                          color="Grade", color_discrete_map={"A":"#10b981", "B":"#3b82f6", "C":"#f59e0b", "F":"#ef4444"})
            fig2.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

# ----------------------------------------------------------------------------
elif selection == "👩‍🎓 Directory & Profiles":
    page_header("Student Directory", "Search, filter, and view detailed academic profiles.")
    
    if df_all.empty:
        st.info("No data available.")
    else:
        tab1, tab2 = st.tabs(["📋 Directory Grid", "👨‍🎓 Detailed Profile"])
        
        with tab1:
            c1, c2 = st.columns([3, 1])
            with c1: search = st.text_input("🔍 Search Name or ID", placeholder="e.g. John Doe")
            with c2: filter_grade = st.multiselect("Filter Grade", ["A", "B", "C", "F"])
            
            filtered = df_all.copy()
            if search:
                filtered = filtered[filtered["Name"].str.contains(search, case=False) | filtered["ID"].astype(str).str.contains(search)]
            if filter_grade:
                filtered = filtered[filtered["Grade"].isin(filter_grade)]
                
            st.dataframe(filtered, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export to CSV", data=convert_df_to_csv(filtered), file_name="directory.csv", mime="text/csv")
            
        with tab2:
            student_id = st.selectbox("Select a Student to view details:", options=df_all["ID"].tolist(), 
                                      format_func=lambda x: f"{x} - {df_all.loc[df_all['ID']==x, 'Name'].values[0]}")
            
            if student_id:
                student = df_all[df_all["ID"] == student_id].iloc[0]
                st.markdown(f"### Profile: {student['Name']}")
                
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Overall Score", f"{student['Score']}/100")
                sc2.metric("Attendance", f"{student['Attendance (%)']}%")
                sc3.metric("Current Grade", student['Grade'])
                
                subj_df = fetch_subjects(student_id)
                if not subj_df.empty:
                    fig = px.bar(subj_df, x="subject_name", y="score", title="Subject Performance", text="score")
                    fig.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=40, b=0))
                    fig.update_traces(marker_color='#3b82f6')
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("No detailed subject data logged yet.")

# ----------------------------------------------------------------------------
elif selection == "📚 Academics & Attendance":
    page_header("Academics & Attendance", "Log individual subject scores and daily attendance.")
    
    if df_all.empty:
        st.warning("Add students before managing subjects or attendance.")
    else:
        tab_subj, tab_att = st.tabs(["📚 Log Subject Score", "🗓️ Log Attendance"])
        
        with tab_subj:
            with st.form("add_subj", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                s_id = c1.selectbox("Student", options=df_all["ID"].tolist(), format_func=lambda x: f"{x} - {df_all.loc[df_all['ID']==x, 'Name'].values[0]}")
                s_name = c2.text_input("Subject Name", placeholder="e.g. Mathematics")
                s_score = c3.slider("Score", 0, 100, 75)
                
                if st.form_submit_button("Add Subject Data"):
                    if s_name:
                        execute_write("INSERT INTO subjects (student_id, subject_name, score) VALUES (?, ?, ?)", (s_id, s_name, s_score))
                        st.toast(f"✅ Added {s_name} score for {s_id}")
                    else:
                        st.error("Subject name is required.")
        
        with tab_att:
            with st.form("add_att", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                a_id = c1.selectbox("Student", options=df_all["ID"].tolist(), format_func=lambda x: f"{x} - {df_all.loc[df_all['ID']==x, 'Name'].values[0]}", key="att_stu")
                a_date = c2.date_input("Date", value=date.today())
                a_pct = c3.slider("Day Attendance (%)", 0, 100, 100)
                
                if st.form_submit_button("Log Attendance"):
                    execute_write("INSERT INTO attendance_log (student_id, log_date, attendance_pct) VALUES (?, ?, ?)", (a_id, a_date.isoformat(), a_pct))
                    st.toast(f"✅ Attendance logged for {a_date}")

# ----------------------------------------------------------------------------
elif selection == "⚙️ Manage Data":
    page_header("Manage Records", "Add, update, remove, or bulk-import student records.")
    
    tab_add, tab_edit, tab_bulk = st.tabs(["➕ Add New", "✏️ Edit / Delete", "📥 Bulk Import"])
    
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n_id = c1.number_input("Student ID", min_value=1, step=1)
            n_name = c2.text_input("Full Name")
            n_score = c1.slider("Overall Score", 0, 100, 75)
            n_att = c2.slider("Attendance (%)", 0, 100, 85)
            
            if st.form_submit_button("Add Student", use_container_width=True):
                if not n_name: st.error("Name required.")
                elif student_id_exists(n_id): st.error("ID already exists.")
                else:
                    execute_write("INSERT INTO students (id, name, grade, score, attendance, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                                  (n_id, n_name.strip(), calculate_grade(n_score), n_score, n_att, datetime.now().isoformat()))
                    st.toast(f"✅ {n_name} added successfully.")
                    st.rerun()

    with tab_edit:
        if df_all.empty:
            st.info("No students to manage.")
        else:
            e_id = st.selectbox("Select Student", options=df_all["ID"].tolist(), format_func=lambda x: f"{x} - {df_all.loc[df_all['ID']==x, 'Name'].values[0]}")
            curr = df_all[df_all["ID"] == e_id].iloc[0]
            
            with st.form("edit_form"):
                e_name = st.text_input("Name", value=curr["Name"])
                e_score = st.slider("Score", 0, 100, int(curr["Score"]))
                e_att = st.slider("Attendance", 0, 100, int(curr["Attendance (%)"]))
                
                c1, c2 = st.columns(2)
                if c1.form_submit_button("💾 Save Changes", use_container_width=True):
                    execute_write("UPDATE students SET name=?, grade=?, score=?, attendance=? WHERE id=?", 
                                  (e_name.strip(), calculate_grade(e_score), e_score, e_att, e_id))
                    st.toast("✅ Student updated.")
                    st.rerun()
                    
            if st.button("🗑️ Delete Student (Danger)", type="primary"):
                execute_write("DELETE FROM students WHERE id=?", (e_id,))
                st.toast("🗑️ Student removed.")
                st.rerun()

    with tab_bulk:
        st.markdown("Upload a CSV file containing `ID`, `Name`, `Score`, and `Attendance` headers.")
        csv_file = st.file_uploader("Choose CSV", type=["csv"])
        if csv_file:
            try:
                import_df = pd.read_csv(csv_file)
                if not {"ID", "Name", "Score", "Attendance"}.issubset(set(import_df.columns)):
                    st.error("Missing required columns: ID, Name, Score, Attendance")
                else:
                    st.dataframe(import_df.head(3), hide_index=True)
                    if st.button("Confirm Import", use_container_width=True):
                        added = 0
                        for _, row in import_df.iterrows():
                            sid = int(row["ID"])
                            if not student_id_exists(sid) and pd.notna(row["Name"]):
                                execute_write("INSERT INTO students (id, name, grade, score, attendance, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                              (sid, str(row["Name"]), calculate_grade(int(row["Score"])), int(row["Score"]), int(row["Attendance"]), datetime.now().isoformat()))
                                added += 1
                        st.success(f"✅ Bulk import complete. Added {added} students.")
            except Exception as e:
                st.error(f"Error processing CSV: {e}")

# ----------------------------------------------------------------------------
elif selection == "🤖 AI Insights":
    page_header(
        "AI Data Assistant",
        "Ask natural-language questions about your classroom's performance."
    )

    if not GEMINI_API_KEY:
        st.warning(
            "⚠️ Gemini API Key is missing. "
            "Please add GEMINI_API_KEY to your Streamlit Secrets."
        )
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": (
                        "Hello! 👋 I can analyze your student data. "
                        "Ask me about scores, attendance, grades, "
                        "top performers, or students needing attention."
                    ),
                }
            ]

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        st.markdown(
            """
            <div class="ai-section-title">
                <div class="ai-title-icon">✦</div>
                <div>
                    <div class="ai-title">Ask the AI</div>
                    <div class="ai-subtitle">Get insights from your live student performance data</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # st.form allows the Enter key to submit the question on desktop
        # and mobile browsers.
        with st.form(
            key=f"ai_form_{st.session_state.ai_input_version}",
            clear_on_submit=True,
        ):
            prompt = st.text_input(
                "Your question",
                placeholder="Ask about students, scores, attendance, or performance...",
                label_visibility="collapsed",
            )
            send_clicked = st.form_submit_button(
                "✦  Ask AI",
                use_container_width=True,
            )

        if send_clicked and prompt.strip():
            question = prompt.strip()
            st.session_state.messages.append({"role": "user", "content": question})

            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing your student data..."):
                    try:
                        subjects_data = fetch_subjects()
                        attendance_data = fetch_attendance_log()

                        context = (
                            "STUDENT DATA:\n" + df_all.to_string(index=False)
                            + "\n\nSUBJECT DATA:\n" + subjects_data.to_string(index=False)
                            + "\n\nATTENDANCE DATA:\n" + attendance_data.to_string(index=False)
                        )

                        system_prompt = """
You are an AI assistant for a Student Performance and Management System.
Use the supplied database information as the source of truth.
Never invent student information, scores, grades, subjects, or attendance.
You may calculate averages, rankings, counts, and comparisons.
If information is unavailable, clearly say so.
Keep answers concise and useful.
Give academic recommendations when requested.
Never reveal passwords, API keys, tokens, database URLs, or secrets.
"""

                        conversation = "\n".join(
                            f"{m['role'].upper()}: {m['content']}"
                            for m in st.session_state.messages[-8:]
                        )

                        full_prompt = f"""
{system_prompt}

DATABASE INFORMATION:
{context}

RECENT CONVERSATION:
{conversation}

USER QUESTION:
{question}
"""

                        client = genai.Client(api_key=GEMINI_API_KEY)
                        response = client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=full_prompt,
                        )

                        answer = (
                            response.text
                            if getattr(response, "text", None)
                            else "Sorry, I couldn't generate an answer."
                        )
                        st.write(answer)

                        st.session_state.messages.append(
                            {"role": "assistant", "content": answer}
                        )
                        st.session_state.ai_input_version += 1
                        st.rerun()

                    except Exception as e:
                        st.error("AI Assistant Error")
                        st.code(str(e), language="text")

        elif send_clicked:
            st.warning("Please enter a question first.")

        if len(st.session_state.messages) > 1:
            if st.button("🗑️  Clear Chat History", key="clear_ai_history"):
                st.session_state.messages = [{
                    "role": "assistant",
                    "content": "Hello! 👋 I can analyze your student data. What would you like to know?"
                }]
                st.session_state.ai_input_version += 1
                st.rerun()

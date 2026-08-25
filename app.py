import streamlit as st
import pandas as pd
import hmac
import os
import html
import time
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import libsql
from groq import Groq
import base64
import io
import random

# ----------------------------------------------------------------------------
# PAGE CONFIGURATION
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="StudentHub OS Advanced",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------------
# SECRETS & AUTH CONFIG
# ----------------------------------------------------------------------------
def _secret(name: str, default=None):
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    if value is not None and str(value).strip():
        return value
    return os.getenv(name, default)

TURSO_DATABASE_URL = _secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _secret("TURSO_AUTH_TOKEN")
GROQ_API_KEY = _secret("GROQ_API_KEY")
GROQ_MODEL = _secret("GROQ_MODEL", "mixtral-8x7b-32768")

ADMIN_USERNAME_CONFIGURED = _secret("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_CONFIGURED = _secret("ADMIN_PASSWORD", "admin123")

def check_login(username: str, password: str) -> bool:
    if not ADMIN_USERNAME_CONFIGURED or not ADMIN_PASSWORD_CONFIGURED:
        return False
    return (
        hmac.compare_digest(username, str(ADMIN_USERNAME_CONFIGURED))
        and hmac.compare_digest(password, str(ADMIN_PASSWORD_CONFIGURED))
    )

# ----------------------------------------------------------------------------
# ADVANCED CSS INJECTION
# ----------------------------------------------------------------------------
st.markdown("""
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    .stApp {
        background: linear-gradient(145deg, #0b1220 0%, #111827 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp > header { background: transparent !important; }
    
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #1e293b; border-radius: 10px; }
    ::-webkit-scrollbar-thumb { background: #ff4b4b; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #ff6b57; }

    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255,255,255,0.05) !important;
        padding: 20px 12px !important;
    }
    [data-testid="stSidebar"] * { color: #f1f5f9 !important; }
    [data-testid="stSidebar"] .stMarkdown h3 {
        font-size: 1.4rem;
        font-weight: 800;
        background: linear-gradient(to right, #f8fafc, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 0 8px;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(148,163,184,0.08) !important;
        margin: 16px 0 !important;
    }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 4px !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        padding: 10px 16px !important;
        border-radius: 14px !important;
        transition: 0.25s ease !important;
        border: 1px solid transparent !important;
        font-weight: 500 !important;
        background: transparent !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.04) !important;
        border-color: rgba(255,255,255,0.06) !important;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[data-selected="true"] {
        background: linear-gradient(135deg, rgba(255,75,75,0.12), rgba(255,107,87,0.05)) !important;
        border-color: rgba(255,75,75,0.2) !important;
        box-shadow: 0 4px 16px rgba(255,75,75,0.08) !important;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[data-selected="true"] .stMarkdown {
        color: #f8fafc !important;
    }

    [data-testid="stSidebar"] div[data-testid="stMetric"] {
        background: rgba(30,41,59,0.6) !important;
        border: 1px solid rgba(255,255,255,0.04) !important;
        border-radius: 18px !important;
        padding: 16px 18px !important;
        backdrop-filter: blur(8px) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-size: 1.8rem !important;
        font-weight: 800 !important;
    }

    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        min-height: 48px !important;
        border-radius: 16px !important;
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        transition: 0.25s ease !important;
        margin-top: 8px !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,75,75,0.08) !important;
        border-color: rgba(255,75,75,0.15) !important;
        color: #f8fafc !important;
        transform: translateY(-1px);
    }

    .block-container {
        padding: 20px 24px 40px !important;
        max-width: 1400px !important;
    }

    .hero-header {
        background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9));
        backdrop-filter: blur(12px);
        border-radius: 28px;
        padding: 28px 32px;
        margin-bottom: 28px;
        border: 1px solid rgba(255,255,255,0.04);
        box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        position: relative;
        overflow: hidden;
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(255,75,75,0.06), transparent 70%);
        border-radius: 50%;
        pointer-events: none;
    }
    .hero-header h1 {
        font-size: 2rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: -0.5px;
        margin: 0;
        position: relative;
        z-index: 1;
    }
    .hero-header p {
        color: #94a3b8;
        font-size: 1rem;
        margin: 6px 0 0;
        position: relative;
        z-index: 1;
    }
    .hero-header .badge {
        display: inline-block;
        background: rgba(255,75,75,0.12);
        padding: 4px 14px;
        border-radius: 60px;
        font-size: 0.7rem;
        color: #ff6b57;
        font-weight: 600;
        letter-spacing: 0.3px;
        border: 1px solid rgba(255,75,75,0.1);
        margin-top: 8px;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 28px;
    }
    .metric-card {
        background: rgba(15,23,42,0.6);
        backdrop-filter: blur(8px);
        border-radius: 20px;
        padding: 20px 22px;
        border: 1px solid rgba(255,255,255,0.03);
        transition: 0.25s ease;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .metric-card:hover {
        border-color: rgba(255,255,255,0.08);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    }
    .metric-card .label {
        font-size: 0.7rem;
        text-transform: uppercase;
        color: #94a3b8;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-card .value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #f8fafc;
        margin: 6px 0 2px;
        line-height: 1.1;
    }
    .metric-card .sub {
        font-size: 0.75rem;
        color: #10b981;
        font-weight: 500;
    }
    .metric-card .sub.warning { color: #f59e0b; }
    .metric-card .sub.danger { color: #ef4444; }

    .glass-card {
        background: rgba(15,23,42,0.5);
        backdrop-filter: blur(8px);
        border-radius: 24px;
        padding: 24px 28px;
        border: 1px solid rgba(255,255,255,0.03);
        box-shadow: 0 8px 32px rgba(0,0,0,0.12);
        margin-bottom: 24px;
        transition: 0.25s ease;
    }
    .glass-card:hover {
        border-color: rgba(255,255,255,0.06);
    }
    .glass-card .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .glass-card .card-title i {
        color: #ff4b4b;
    }

    .stForm {
        background: rgba(15,23,42,0.5) !important;
        backdrop-filter: blur(8px) !important;
        border: 1px solid rgba(255,255,255,0.04) !important;
        border-radius: 24px !important;
        padding: 24px 28px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1) !important;
    }
    .stForm input, .stForm select, .stForm textarea {
        background: rgba(0,0,0,0.3) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 14px !important;
        color: #f1f5f9 !important;
        padding: 12px 16px !important;
        font-size: 0.95rem !important;
        transition: 0.2s ease !important;
    }
    .stForm input:focus, .stForm select:focus {
        border-color: #ff4b4b !important;
        box-shadow: 0 0 0 3px rgba(255,75,75,0.1) !important;
    }
    .stForm label {
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
    }
    .stForm button[kind="formSubmit"] {
        background: linear-gradient(135deg, #ff4b4b, #ff6b57) !important;
        border: none !important;
        border-radius: 60px !important;
        padding: 12px 32px !important;
        font-weight: 700 !important;
        color: white !important;
        box-shadow: 0 8px 24px rgba(255,75,75,0.2) !important;
        transition: 0.25s ease !important;
        min-height: 48px !important;
    }
    .stForm button[kind="formSubmit"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 32px rgba(255,75,75,0.3) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background: rgba(15,23,42,0.4) !important;
        border-radius: 16px !important;
        padding: 6px !important;
        border: 1px solid rgba(255,255,255,0.03) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        transition: 0.2s ease !important;
        height: auto !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #f8fafc !important;
        background: rgba(255,255,255,0.03) !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(255,75,75,0.1) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255,75,75,0.1) !important;
    }

    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 8px 4px;
        margin-bottom: 16px;
    }
    .chat-message {
        padding: 14px 20px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 85%;
        animation: fadeIn 0.3s ease;
    }
    .chat-message.user {
        background: linear-gradient(135deg, rgba(255,75,75,0.12), rgba(255,107,87,0.05));
        border: 1px solid rgba(255,75,75,0.08);
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }
    .chat-message.assistant {
        background: rgba(15,23,42,0.6);
        border: 1px solid rgba(255,255,255,0.04);
        border-left: 3px solid #ff4b4b;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }
    .chat-message .role-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        color: #64748b;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .chat-message .content {
        color: #e2e8f0;
        line-height: 1.6;
        font-size: 0.95rem;
    }
    .chat-message.user .content { color: #f8fafc; }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .login-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 90vh;
        position: relative;
    }
    .login-wrapper::before {
        content: '';
        position: fixed;
        top: -30%;
        left: -20%;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, rgba(255,75,75,0.08), transparent 70%);
        border-radius: 50%;
        filter: blur(60px);
        animation: floatBlob 10s ease-in-out infinite;
        pointer-events: none;
    }
    .login-wrapper::after {
        content: '';
        position: fixed;
        bottom: -30%;
        right: -20%;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, rgba(59,130,246,0.08), transparent 70%);
        border-radius: 50%;
        filter: blur(60px);
        animation: floatBlob 12s ease-in-out infinite reverse;
        pointer-events: none;
    }
    @keyframes floatBlob {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(30px, 40px) scale(1.1); }
    }
    .login-card {
        width: 100%;
        max-width: 420px;
        background: rgba(15,23,42,0.7);
        backdrop-filter: blur(24px);
        border: 1px solid rgba(255,255,255,0.04);
        border-radius: 32px;
        padding: 44px 40px 36px;
        box-shadow: 0 24px 80px rgba(0,0,0,0.5);
        position: relative;
        z-index: 1;
        animation: cardRise 0.5s ease-out;
    }
    @keyframes cardRise {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .login-badge {
        width: 72px;
        height: 72px;
        margin: 0 auto 20px;
        border-radius: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #ff4b4b, #ff7a59);
        font-size: 32px;
        box-shadow: 0 12px 40px rgba(255,75,75,0.3);
    }
    .login-title {
        text-align: center;
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0 0 4px;
    }
    .login-subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 0.9rem;
        margin: 0 0 28px;
    }
    .login-card .stForm {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    .login-card .stTextInput label {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600 !important;
    }
    .login-card .stTextInput input {
        background: rgba(0,0,0,0.3) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #f8fafc !important;
        border-radius: 14px !important;
        min-height: 50px !important;
    }
    .login-card .stTextInput input:focus {
        border-color: #ff4b4b !important;
        box-shadow: 0 0 0 3px rgba(255,75,75,0.1) !important;
    }
    .login-card .stButton > button {
        width: 100% !important;
        min-height: 52px !important;
        background: linear-gradient(135deg, #ff4b4b, #ff6b57) !important;
        color: white !important;
        border: none !important;
        border-radius: 60px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        box-shadow: 0 8px 24px rgba(255,75,75,0.2) !important;
        transition: 0.25s ease !important;
        margin-top: 4px !important;
    }
    .login-card .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 32px rgba(255,75,75,0.35) !important;
    }
    .login-footer {
        text-align: center;
        margin-top: 20px;
        color: #475569;
        font-size: 0.7rem;
        letter-spacing: 0.3px;
    }
    .login-lockout {
        background: rgba(239,68,68,0.08);
        border: 1px solid rgba(239,68,68,0.15);
        color: #fca5a5;
        padding: 12px 16px;
        border-radius: 14px;
        font-size: 0.85rem;
        text-align: center;
        margin-bottom: 16px;
    }

    .ai-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 20px;
    }
    .ai-icon {
        width: 56px;
        height: 56px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #ff4b4b, #ff7a59);
        font-size: 26px;
        box-shadow: 0 8px 24px rgba(255,75,75,0.2);
    }
    .ai-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
    }
    .ai-subtitle {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    @media (max-width: 768px) {
        .block-container { padding: 12px 16px !important; }
        .hero-header { padding: 20px !important; border-radius: 20px !important; }
        .hero-header h1 { font-size: 1.4rem !important; }
        .metric-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 10px !important; }
        .metric-card { padding: 14px 16px !important; }
        .metric-card .value { font-size: 1.6rem !important; }
        .glass-card { padding: 16px 18px !important; border-radius: 18px !important; }
        .stForm { padding: 16px 18px !important; }
        .login-card { padding: 28px 24px !important; margin: 0 12px !important; }
        .chat-message { max-width: 95% !important; }
        .ai-title { font-size: 1.2rem !important; }
        .ai-icon { width: 44px; height: 44px; font-size: 20px; }
        [data-testid="stSidebar"] { padding: 12px 8px !important; }
        [data-testid="stSidebar"] .stRadio label { padding: 8px 12px !important; font-size: 0.85rem !important; }
    }
    @media (max-width: 480px) {
        .metric-grid { grid-template-columns: 1fr 1fr !important; gap: 8px !important; }
        .metric-card .value { font-size: 1.3rem !important; }
        .metric-card .label { font-size: 0.6rem !important; }
    }

    .text-gradient {
        background: linear-gradient(to right, #f8fafc, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .mt-2 { margin-top: 16px; }
    .mb-2 { margin-bottom: 16px; }
    .gap-2 { gap: 12px; }
    .flex { display: flex; align-items: center; }
    .flex-between { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
    .badge-pill {
        display: inline-block;
        padding: 2px 12px;
        border-radius: 60px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .badge-green { background: rgba(16,185,129,0.12); color: #10b981; border: 1px solid rgba(16,185,129,0.1); }
    .badge-blue { background: rgba(59,130,246,0.12); color: #3b82f6; border: 1px solid rgba(59,130,246,0.1); }
    .badge-yellow { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.1); }
    .badge-red { background: rgba(239,68,68,0.12); color: #ef4444; border: 1px solid rgba(239,68,68,0.1); }
</style>
""", unsafe_allow_html=True)

def page_header(title, subtitle):
    st.markdown(f"""
        <div class="hero-header">
            <h1>{html.escape(str(title))}</h1>
            <p>{html.escape(str(subtitle))}</p>
        </div>
    """, unsafe_allow_html=True)

def metric_card(label, value, note="", note_type=""):
    st.markdown(f"""
        <div class="metric-card">
            <div class="label">{html.escape(str(label))}</div>
            <div class="value">{html.escape(str(value))}</div>
            <div class="sub {html.escape(str(note_type))}">{html.escape(str(note))}</div>
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
# INITIALIZATION
# ----------------------------------------------------------------------------
init_db()

# ----------------------------------------------------------------------------
# AUTHENTICATION
# ----------------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60
SESSION_TIMEOUT_MINUTES = 30

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "lockout_until" not in st.session_state:
    st.session_state.lockout_until = 0
if "last_active" not in st.session_state:
    st.session_state.last_active = time.time()
if "username" not in st.session_state:
    st.session_state.username = ""

if st.session_state.logged_in:
    if time.time() - st.session_state.last_active > SESSION_TIMEOUT_MINUTES * 60:
        st.session_state.logged_in = False
        st.warning("⏱️ Session expired due to inactivity. Please log in again.")
    else:
        st.session_state.last_active = time.time()

if not st.session_state.logged_in:
    if not ADMIN_USERNAME_CONFIGURED or not ADMIN_PASSWORD_CONFIGURED:
        st.error(
            "⚠️ Admin credentials are not configured. "
            "Set ADMIN_USERNAME and ADMIN_PASSWORD in Streamlit Secrets before using this app."
        )
        st.stop()

    st.markdown('<div class="login-wrapper"><div class="login-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="login-badge">🎓</div>
        <div class="login-title">StudentHub OS</div>
        <div class="login-subtitle">Secure Admin Portal · Sign in to continue</div>
    """, unsafe_allow_html=True)

    now = time.time()
    locked_out = now < st.session_state.lockout_until

    if locked_out:
        remaining = int(st.session_state.lockout_until - now)
        st.markdown(
            f'<div class="login-lockout">🔒 Too many failed attempts. Try again in {remaining}s.</div>',
            unsafe_allow_html=True
        )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="admin", disabled=locked_out)
        password = st.text_input("Password", type="password", placeholder="••••••••", disabled=locked_out)
        submitted = st.form_submit_button("Authenticate →", use_container_width=True, disabled=locked_out)

        if submitted and not locked_out:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.login_attempts = 0
                st.session_state.last_active = time.time()
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                remaining_attempts = MAX_LOGIN_ATTEMPTS - st.session_state.login_attempts
                if st.session_state.login_attempts >= MAX_LOGIN_ATTEMPTS:
                    st.session_state.lockout_until = time.time() + LOCKOUT_SECONDS
                    st.session_state.login_attempts = 0
                    st.rerun()
                else:
                    st.error(f"❌ Invalid credentials. {remaining_attempts} attempt(s) left before temporary lockout.")

    st.markdown('<div class="login-footer">Protected access · Unauthorized entry is prohibited</div>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.stop()

# ----------------------------------------------------------------------------
# SIDEBAR

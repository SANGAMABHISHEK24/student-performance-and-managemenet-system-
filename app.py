st.markdown("""
    <style>
    /* ... your existing global styles stay as-is above this ... */

    /* ================= LOGIN PAGE ================= */
    .stApp:has(.login-wrapper) {
        background: radial-gradient(circle at 20% 20%, #1e293b 0%, #0f172a 50%, #020617 100%);
    }

    .login-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 85vh;
        position: relative;
    }

    .login-wrapper::before {
        content: "";
        position: fixed;
        top: -20%;
        left: -10%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(255,75,75,0.15) 0%, transparent 70%);
        border-radius: 50%;
        filter: blur(40px);
        animation: floatBlob 8s ease-in-out infinite;
        pointer-events: none;
    }

    .login-wrapper::after {
        content: "";
        position: fixed;
        bottom: -20%;
        right: -10%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%);
        border-radius: 50%;
        filter: blur(40px);
        animation: floatBlob 10s ease-in-out infinite reverse;
        pointer-events: none;
    }

    @keyframes floatBlob {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(30px, 40px) scale(1.1); }
    }

    .login-card {
        width: 100%;
        max-width: 420px;
        background: rgba(30, 41, 59, 0.55);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 24px;
        padding: 40px 36px 28px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
        animation: cardRise 0.5s ease-out;
    }

    @keyframes cardRise {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .login-badge {
        width: 64px; height: 64px;
        margin: 0 auto 18px;
        border-radius: 18px;
        display: flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #ff4b4b, #ff7a59);
        font-size: 30px;
        box-shadow: 0 10px 30px rgba(255,75,75,0.35);
    }

    .login-title {
        text-align: center;
        color: #f8fafc;
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0 0 4px;
    }

    .login-subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 0.9rem;
        margin: 0 0 26px;
    }

    .login-wrapper div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    .login-wrapper div[data-testid="stTextInput"] label {
        color: #cbd5e1 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .login-wrapper div[data-testid="stTextInput"] input {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        color: #f8fafc !important;
        border-radius: 12px !important;
        min-height: 48px !important;
        font-size: 15px !important;
    }

    .login-wrapper div[data-testid="stTextInput"] input:focus {
        border-color: #ff4b4b !important;
        box-shadow: 0 0 0 3px rgba(255,75,75,0.15) !important;
    }

    .login-wrapper .stButton > button,
    .login-wrapper button[kind="formSubmit"] {
        width: 100%;
        min-height: 50px;
        margin-top: 8px;
        background: linear-gradient(135deg, #ff4b4b, #ff6b57) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        box-shadow: 0 8px 20px rgba(255,75,75,0.25);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .login-wrapper .stButton > button:hover,
    .login-wrapper button[kind="formSubmit"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 26px rgba(255,75,75,0.35);
    }

    .login-footer {
        text-align: center;
        margin-top: 20px;
        color: #475569;
        font-size: 0.75rem;
    }

    .login-lockout {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        padding: 10px 14px;
        border-radius: 10px;
        font-size: 0.85rem;
        text-align: center;
        margin-bottom: 16px;
    }
    </style>
""", unsafe_allow_html=True)

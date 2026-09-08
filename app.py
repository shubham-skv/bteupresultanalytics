"""
app.py  —  BTEUP Analytics Suite — Main entry point
Run with: streamlit run app.py
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.db import get_student_count, get_result_count, get_institutes
from views import nominal, fetch, analytics

st.set_page_config(
    page_title="BTEUP Analytics Suite",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "page" not in st.session_state:
    st.session_state.page = "home"

# ── Global styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background-color: #f8fafc;
    color: #1e293b;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0;
}

/* Sidebar nav buttons */
.nav-btn {
    display: block;
    width: 100%;
    padding: 10px 15px;
    margin-bottom: 8px;
    border-radius: 8px;
    background: transparent;
    color: #475569;
    text-decoration: none;
    font-weight: 500;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    cursor: pointer;
    text-align: left;
}
.nav-btn:hover {
    background: #f1f5f9;
    color: #0f172a;
}
.nav-btn.active {
    background: #e0e7ff;
    border: 1px solid #c7d2fe;
    color: #4f46e5;
}

/* Cards */
.metric-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}
.metric-card h2 { font-size: 2.5rem; font-weight: 700; margin: 0; }
.metric-card p  { color: #64748b; margin: 0; font-size: 0.95rem; font-weight: 500; }

/* Buttons */
.stButton > button {
    background: #4f46e5 !important;
    color: #000000 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2) !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 12px -2px rgba(79, 70, 229, 0.3) !important;
    background: #4338ca !important;
    color: #ffffff !important;
}

/* Tables */
.stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }
thead th {
    background: #f1f5f9 !important;
    color: #334155 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #e2e8f0 !important;
}

/* Section headers */
.section-header {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.5rem;
}

/* Status pills */
.pill-pass { background:#dcfce7; color:#166534; padding:2px 10px; border-radius:12px; font-size:0.8rem; font-weight:600; }
.pill-fail { background:#fee2e2; color:#991b1b; padding:2px 10px; border-radius:12px; font-size:0.8rem; font-weight:600; }

/* Analytics UI components */
.kpi-card { background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:1.2rem 1.5rem; text-align:center; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1); }
.kpi-val { font-size:2.2rem; font-weight:700; line-height:1; }
.kpi-lbl { font-size:0.85rem; color:#64748b; margin-top:4px; font-weight:500; }
.topper-card { background:linear-gradient(135deg,#f0f9ff,#e0e7ff); border:1px solid #c7d2fe; border-radius:14px; padding:1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
.topper-rank { font-size:2.2rem; }
.topper-name { font-size:1.1rem; font-weight:700; color:#1e293b; }
.topper-score { font-size:0.9rem; color:#4f46e5; font-weight:600; }

.info-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 1rem 1.5rem; margin: 1rem 0; }
.branch-chip { display:inline-block; background:#dbeafe; border:1px solid #93c5fd; border-radius:20px; padding:4px 14px; margin:4px; font-size:0.85rem; color:#1d4ed8; font-weight:500; }
.stat-row { display:flex; gap:1rem; margin-bottom:1rem; }
.stat-chip { background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:0.7rem 1.2rem; flex:1; text-align:center; box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05); }
.stat-chip .val { font-size:1.6rem; font-weight:700; color:#0f172a; }
.stat-chip .lbl { font-size:0.8rem; color:#64748b; font-weight:500; }

</style>
""", unsafe_allow_html=True)

# ── Sidebar Navigation ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 BTEUP Suite")
    st.markdown("---")
    
    institutes = get_institutes()
    if institutes:
        selected_inst = st.selectbox("🏢 Select Your Institute", ["All Institutes"] + institutes, key="global_institute")
        if selected_inst == "All Institutes":
            st.session_state.current_institute = None
        else:
            st.session_state.current_institute = selected_inst
    else:
        st.session_state.current_institute = None
        
    student_count = get_student_count(st.session_state.current_institute)
    result_count  = get_result_count(st.session_state.current_institute)
    
    st.metric("Students in DB", student_count)
    st.metric("Results Fetched", result_count)
    st.markdown("---")
    
    st.markdown("**Navigation**")
    
    def nav_button(label, page_id, icon=""):
        # Make a quick button that switches session state
        is_active = (st.session_state.page == page_id)
        if st.button(f"{icon} {label}", key=f"nav_{page_id}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.page = page_id
            st.rerun()

    nav_button("Home", "home", "🏠")
    nav_button("Upload Nominal", "nominal", "📋")
    nav_button("Fetch Results", "fetch", "🌐")
    nav_button("Analytics", "analytics", "📊")
    nav_button("Settings & Data", "settings", "⚙️")

    st.markdown("---")
    
    with st.expander("💾 Database Backup & Restore", expanded=False):
        st.markdown("<small>Streamlit Cloud deletes files on reboot. Download a backup of your database to keep it safe.</small>", unsafe_allow_html=True)
        
        db_path = os.path.join(os.path.dirname(__file__), "bteup_data.db")
        if os.path.exists(db_path):
            with open(db_path, "rb") as f:
                st.download_button(
                    label="📥 Download Database Backup",
                    data=f,
                    file_name="bteup_data.db",
                    mime="application/octet-stream",
                    use_container_width=True
                )
        
        st.markdown("<small>Restore a previously downloaded database:</small>", unsafe_allow_html=True)
        uploaded_db = st.file_uploader("Upload DB File", type=["db"], label_visibility="collapsed")
        if uploaded_db:
            if st.button("📤 Restore Database", use_container_width=True, type="primary"):
                with open(db_path, "wb") as f:
                    f.write(uploaded_db.getbuffer())
                st.success("Database restored! Please reload the app.")
                st.rerun()

    st.markdown("---")
    st.caption("BTEUP Analytics Suite v2.0")

# ── Routing ──────────────────────────────────────────────────────────────────────
if st.session_state.page == "home":
    st.markdown('<div class="section-header">🎓 BTEUP Analytics Suite</div>', unsafe_allow_html=True)
    st.markdown("Your complete result management and analytics platform for BTEUP students.")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h2 style="color:#6366f1">{student_count}</h2>
            <p>Students Loaded</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h2 style="color:#10b981">{result_count}</h2>
            <p>Results Fetched</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        pct = f"{int(result_count/student_count*100)}%" if student_count else "0%"
        st.markdown(f"""
        <div class="metric-card">
            <h2 style="color:#f59e0b">{pct}</h2>
            <p>Coverage</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    ### How to use this app
    
    Use the **left sidebar** to navigate seamlessly between sections.

    | Step | Section | What to do |
    |------|---------|-----------|
    | 1️⃣ | **📋 Upload Nominal** | Upload your `NOMINAL.xlsx` or a PDF nominal register to build your student database. |
    | 2️⃣ | **🌐 Fetch Results** | Select branches and fetch all results at once directly from the BTEUP portal. |
    | 3️⃣ | **📊 Analytics** | Explore branch-wise, subject-wise results, search for students, view toppers, and export all data. |
    """)

    st.markdown("---")
    st.markdown("### 📥 Quick PDF Download")
    st.markdown("Select a branch to instantly download a ZIP of all individual original BTEUP result PDFs for that branch.")
    try:
        from views.analytics import load_results, build_student_summary
        raw_df = load_results(st.session_state.current_institute)
        if not raw_df.empty:
            student_df = build_student_summary(raw_df)
            branches = sorted([b for b in student_df["branch"].unique() if b])
            
            selected_b = st.selectbox("Select Branch", ["-- Select a branch --"] + branches, key="home_branch_dl")
            if selected_b and selected_b != "-- Select a branch --":
                branch_students = student_df[student_df["branch"] == selected_b].copy()
                st.info(f"Loaded {len(branch_students)} student records for this branch.")
                
                zip_cache_key = f"orig_zip_home_{selected_b}"
                if zip_cache_key not in st.session_state:
                    if st.button("📦 Generate Original PDFs ZIP", key="gen_orig_zip_home", use_container_width=True):
                        prog_bar = st.progress(0)
                        status_text = st.empty()
                        
                        import io, zipfile, base64
                        import requests
                        try:
                            from weasyprint import HTML
                            
                            zip_buffer = io.BytesIO()
                            total = len(branch_students)
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                                for i, (_, row_data) in enumerate(branch_students.iterrows()):
                                    enroll = str(row_data["enrollment"]).strip()
                                    dob = str(row_data.get("dob", "")).strip()
                                    branch_clean = str(row_data.get("branch", "Result")).replace("/", "_").replace(":", "")
                                    
                                    status_text.text(f"Downloading PDF for {enroll}... ({i+1}/{total})")
                                    prog_bar.progress((i + 1) / total)
                                    
                                    enr_b64 = base64.b64encode(enroll.encode()).decode()
                                    dob_b64 = base64.b64encode(dob.encode()).decode()
                                    url = f"https://result.bteexam.com/even/main/oddresult.aspx?id={enr_b64}&id2={dob_b64}"
                                    try:
                                        resp = requests.get(url, verify=False, timeout=15)
                                        if resp.status_code == 200:
                                            html_text = resp.text
                                            css_injection = "<style>@page { size: A3 landscape; margin: 10mm; } table { width: 100% !important; max-width: 100% !important; } body { font-size: 12px; }</style>"
                                            if "</head>" in html_text:
                                                html_text = html_text.replace("</head>", f"{css_injection}</head>")
                                            else:
                                                html_text = css_injection + html_text
                                                
                                            pdf_data = HTML(string=html_text, base_url="https://result.bteexam.com/").write_pdf()
                                            if pdf_data:
                                                zf.writestr(f"{branch_clean}_{enroll}.pdf", pdf_data)
                                    except Exception:
                                        pass
                            
                            status_text.empty()
                            prog_bar.empty()
                            st.session_state[zip_cache_key] = zip_buffer.getvalue()
                            st.rerun()
                        except ImportError:
                            status_text.error("weasyprint is not installed. Please add it to requirements.txt")
                else:
                    file_prefix = f"Original_Results_{selected_b}".replace(' ', '_').replace('/', '_').replace('[', '').replace(']', '')
                    st.success("Original PDFs ZIP generated successfully!")
                    st.download_button("📥 Click here to Download ZIP", data=st.session_state[zip_cache_key], file_name=f"{file_prefix}.zip", mime="application/zip", use_container_width=True, type="primary")
        else:
            st.info("No result data found yet. Fetch results first!")
    except Exception as e:
        pass

elif st.session_state.page == "nominal":
    nominal.render()
elif st.session_state.page == "fetch":
    fetch.render()
elif st.session_state.page == "analytics":
    analytics.render()
elif st.session_state.page == "settings":
    import views.settings as settings
    settings.render()

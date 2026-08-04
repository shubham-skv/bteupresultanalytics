"""
app.py  —  BTEUP Analytics Suite — Main entry point
Run with: streamlit run app.py
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.db import get_student_count, get_result_count
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
    
    student_count = get_student_count()
    result_count  = get_result_count()
    
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
    st.markdown("Select a branch to instantly generate and download its complete result sheet as a PDF.")
    try:
        from views.analytics import load_results, build_student_summary, to_pdf_bytes
        raw_df = load_results()
        if not raw_df.empty:
            student_df = build_student_summary(raw_df)
            branches = sorted([b for b in student_df["branch"].unique() if b])
            
            selected_b = st.selectbox("Select Branch", ["-- Select a branch --"] + branches, key="home_branch_dl")
            if selected_b and selected_b != "-- Select a branch --":
                branch_students = student_df[student_df["branch"] == selected_b].copy()
                display_b = branch_students[["enrollment","student_name","father_name","score","grand_total","status","passed"]].copy()
                display_b["Status"] = display_b.apply(lambda row: f"✅ {row['status']}" if row["passed"] else f"❌ {row['status']}", axis=1)
                display_b = display_b.drop(["status", "passed"], axis=1)
                display_b.index = range(1, len(display_b)+1)
                display_b = display_b.rename(columns={
                    "enrollment":"Enrollment","student_name":"Name","father_name":"Father","score":"Score","grand_total":"Grand Total"
                })
                
                st.info(f"Loaded {len(display_b)} student records for this branch.")
                
                pdf_bytes = to_pdf_bytes(display_b, f"Full Branch Result - {selected_b}")
                
                cache_key = f"pdf_home_{selected_b}"
                if cache_key not in st.session_state:
                    if st.button("🚀 Generate PDF (Includes Photos)", use_container_width=True):
                        with st.spinner(f"Downloading photos and rendering PDF for {len(display_b)} students... Please wait."):
                            st.session_state[cache_key] = to_pdf_bytes(display_b, f"Full Branch Result - {selected_b}")
                        st.rerun()
                else:
                    file_prefix = f"Branch_{selected_b}".replace(' ', '_').replace('/', '_').replace('[', '').replace(']', '')
                    st.success("PDF generated successfully!")
                    st.download_button("📥 Click here to Download PDF", data=st.session_state[cache_key], file_name=f"{file_prefix}.pdf", mime="application/pdf", use_container_width=True, type="primary")
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

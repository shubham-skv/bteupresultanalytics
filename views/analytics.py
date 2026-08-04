import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

from core.db import get_all_results, get_result_count

# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_grand_total(grand_total: str):
    import re
    gt = str(grand_total).strip()
    # Match pattern: "2628 / 3255 SOME STATUS TEXT"
    m = re.search(r'(\d+)\s*/\s*(\d+)\s*(.*)', gt)
    if m:
        score = int(m.group(1))
        max_score = int(m.group(2))
        status = m.group(3).strip()
        pct = round((score / max_score) * 100, 2) if max_score > 0 else 0.0
        return score, max_score, pct, status
    
    # Fallback
    m2 = re.search(r'(\d{3,})', gt)
    score = int(m2.group(1)) if m2 else 0
    return score, 0, 0.0, gt

def is_pass(status: str) -> bool:
    s = str(status).upper()
    return "FAIL" not in s

def is_clear_pass(status: str) -> bool:
    s = str(status).upper()
    return ("FAIL" not in s) and ("BACK" not in s)

def extract_year(branch_str: str) -> str:
    import re
    m = re.search(r'0?(\d+)\s+Sem', str(branch_str), re.IGNORECASE)
    if m:
        sem = int(m.group(1))
        yr = (sem - 1) // 2 + 1
        if yr == 1: return "1st Year"
        elif yr == 2: return "2nd Year"
        elif yr == 3: return "3rd Year"
        else: return f"Year {yr}"
    return "Unknown Year"

def marks_int(val) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return 0

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()

def to_pdf_bytes(df: pd.DataFrame, title: str = "Report") -> bytes:
    try:
        from fpdf import FPDF
    except ImportError:
        return b"Error: fpdf is not installed"
        
    import os
    import tempfile
    import requests
    
    # Add S.No.
    df = df.copy()
    if "S.No" not in df.columns:
        df.insert(0, "S.No", range(1, len(df) + 1))
        
    cols_lower = [str(c).lower() for c in df.columns]
    has_enroll = False
    for c in cols_lower:
        if "enrollment" in c:
            has_enroll = True
            break
            
    if has_enroll:
        df.insert(1, "Photo", "")

    # Dynamic orientation
    is_landscape = len(df.columns) > 6
    orientation = "L" if is_landscape else "P"
    total_w = 277 if is_landscape else 190
    page_h = 190 if is_landscape else 277 # safe trigger height for new page

    pdf = FPDF(orientation=orientation)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title[:50], ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 8)
    
    # Calculate base weight for columns
    w_base = []
    for col in df.columns:
        c = str(col).lower()
        if "s.no" in c: w_base.append(10)
        elif "enrollment" in c: w_base.append(32)
        elif "photo" in c: w_base.append(18)
        elif "name" in c or "father" in c or "topper" in c: w_base.append(35)
        elif "branch" in c or "subject" in c: w_base.append(42)
        elif "status" in c: w_base.append(16)
        elif "obtained" in c: w_base.append(24)
        elif "min" in c or "max" in c: w_base.append(18)
        elif "score" in c or "mark" in c or "percent" in c or "total" in c: w_base.append(20)
        else: w_base.append(20)
        
    # Unconditionally stretch to fill the entire page width
    sum_w = sum(w_base)
    w = [(x / sum_w) * total_w for x in w_base]
        
    line_h = 5
    for i, col in enumerate(df.columns):
        pdf.cell(w[i], line_h * 2, str(col)[:15], border=1, align="C")
    pdf.ln()
    
    pdf.set_font("Arial", "", 8)
    
    # Dummy PDF for exact height calculation
    dummy = FPDF(orientation=orientation)
    dummy.add_page()
    dummy.set_font("Arial", "", 8)
    
    for _, row in df.iterrows():
        # Clean text
        row_strs = []
        for col in df.columns:
            val = str(row[col]).encode('latin-1', 'ignore').decode('latin-1').strip()
            row_strs.append(val)
            
        # Calculate exact max height
        max_h = line_h
        for i, val in enumerate(row_strs):
            dummy.set_xy(10, 10)
            dummy.multi_cell(w[i], line_h, val)
            h = dummy.get_y() - 10
            if h > max_h:
                max_h = h
                
        if has_enroll:
            max_h = max(max_h, 22) # ensure room for photo
            
        row_h = max_h
        
        if pdf.get_y() + row_h > page_h:
            pdf.add_page()
            # Reprint headers
            pdf.set_font("Arial", "B", 8)
            for i, col in enumerate(df.columns):
                pdf.cell(w[i], line_h * 2, str(col)[:15], border=1, align="C")
            pdf.ln()
            pdf.set_font("Arial", "", 8)
            
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        
        for i, val in enumerate(row_strs):
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.rect(x, y, w[i], row_h)
            
            c_name = str(df.columns[i]).lower()
            if c_name == "photo" and has_enroll:
                # get enrollment val
                enr_val = str(row.get("enrollment", row.get("Enrollment", ""))).strip()
                if enr_val:
                    img_url = f"https://bteup.ac.in/PDFFILES/STUDENTIMAGES/P{enr_val}.jpg"
                    img_path = os.path.join(tempfile.gettempdir(), f"{enr_val}.jpg")
                    if not os.path.exists(img_path):
                        try:
                            r = requests.get(img_url, timeout=2)
                            if r.status_code == 200:
                                with open(img_path, "wb") as f:
                                    f.write(r.content)
                                from PIL import Image, ImageOps
                                with Image.open(img_path) as im:
                                    im = ImageOps.exif_transpose(im)
                                    im = im.convert("RGB")
                                    im = ImageOps.fit(im, (140, 180), Image.Resampling.LANCZOS)
                                    im.save(img_path, "JPEG", quality=85)
                        except:
                            pass
                    if os.path.exists(img_path):
                        try:
                            img_h = 18
                            img_w = 14
                            img_y = y + (row_h - img_h) / 2
                            if img_y < y + 1: img_y = y + 1
                            img_x = x + (w[i] - img_w) / 2
                            pdf.image(img_path, x=img_x, y=img_y, w=img_w, h=img_h)
                        except:
                            pass
            else:
                pdf.multi_cell(w[i], line_h, val, border=0, align="L")
                
            pdf.set_xy(x + w[i], y)
            
        pdf.set_xy(start_x, start_y + row_h)
        
    out = pdf.output(dest="S")
    if isinstance(out, str):
        out = out.encode("latin-1")
    return out

def render_download_buttons(df: pd.DataFrame, prefix: str):
    col1, col2, col3, col4 = st.columns(4)
    file_prefix = prefix.lower().replace(' ', '_').replace('/', '_')
    with col1:
        st.download_button(f"📥 CSV", data=df.to_csv(index=False).encode("utf-8"), file_name=f"{file_prefix}.csv", mime="text/csv", use_container_width=True, key=f"dl_csv_{file_prefix}")
    with col2:
        cache_key = f"pdf_bytes_{file_prefix}"
        if cache_key not in st.session_state:
            if st.button("🚀 Prepare PDF", key=f"prep_pdf_{file_prefix}", use_container_width=True):
                with st.spinner(f"Preparing PDF for {len(df)} records..."):
                    st.session_state[cache_key] = to_pdf_bytes(df, title=prefix)
                st.rerun()
        else:
            st.download_button(f"📥 Download PDF", data=st.session_state[cache_key], file_name=f"{file_prefix}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_{file_prefix}")


def check_pass(r):
    mo = r["marks_obtained_int"]
    mi = r["min_marks_int"]
    mx = r["max_marks_int"]
    paper = str(r["paper_name"]).upper()
    
    if "CARRY OVER" in paper:
        return True # no pass/fail for carry over
    if mi > 0:
        return mo >= mi
    if "SESSIONAL" in paper:
        return mo >= (mx * 0.5)
    return True # default to pass if no specific rules apply and min_marks is 0

@st.cache_data(ttl=30)
def load_results():
    df = get_all_results()
    df["branch"] = df["branch"].str.replace("Semster", "Semester")
    df["marks_obtained_int"] = df["marks_obtained"].apply(marks_int)
    df["max_marks_int"]      = df["max_marks"].apply(marks_int)
    df["min_marks_int"]      = df["min_marks"].apply(marks_int)
    df["is_pass_subject"]    = df.apply(check_pass, axis=1)
    df["subject_display"] = df["paper_code"] + " - " + df["paper_name"]
    return df

@st.cache_data(ttl=30)
def build_student_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = df.groupby(["enrollment", "student_name", "father_name", "branch", "grand_total", "dob"]).agg(
        subjects_attempted=("paper_name", "count"),
        total_obtained=("marks_obtained_int", "sum"),
    ).reset_index()
    
    parsed = summary["grand_total"].apply(lambda x: pd.Series(parse_grand_total(x)))
    parsed.columns = ["score", "max_score", "percentage", "status"]
    
    summary = pd.concat([summary, parsed], axis=1)
    summary["passed"] = summary["status"].apply(is_pass)
    summary["clear_pass"] = summary["status"].apply(is_clear_pass)
    summary["year"] = summary["branch"].apply(extract_year)
    
    return summary.sort_values("percentage", ascending=False).reset_index(drop=True)

def render():
    st.markdown('<div class="section-header">📊 Analytics Dashboard</div>', unsafe_allow_html=True)

    result_count = get_result_count()
    if result_count == 0:
        st.warning("⚠️ No results in database yet. Please go to **🌐 Fetch Results** to download results first.")
        return

    raw_df = load_results()
    student_df = build_student_summary(raw_df)

    # ── Global KPIs ───────────────────────────────────────────────────────────────
    total_students = len(student_df)
    clear_pass_count = student_df["clear_pass"].sum()
    passed_with_back = student_df["passed"].sum() - clear_pass_count
    fail_count     = total_students - clear_pass_count - passed_with_back
    pass_pct       = round(clear_pass_count / total_students * 100, 1) if total_students else 0
    avg_score      = round(student_df["score"].mean(), 1) if total_students else 0
    top_score      = student_df["score"].max() if total_students else 0
    branches       = sorted(raw_df["branch"].dropna().unique().tolist())
    subjects       = sorted(raw_df["subject_display"].dropna().unique().tolist())

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (total_students, "Total Students", "#6366f1"),
        (clear_pass_count, "Clear Pass", "#10b981"),
        (passed_with_back, "Pass w/ Back", "#f59e0b"),
        (fail_count, "Failed", "#ef4444"),
        (f"{pass_pct}%", "Clear Pass Rate", "#3b82f6"),
    ]
    for col, (val, lbl, color) in zip([c1, c2, c3, c4, c5], kpis):
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-val" style="color:{color}">{val}</div>
            <div class="kpi-lbl">{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── TABS ─────────────────────────────────────────────────────────────────────
    tab_overview, tab_branch, tab_subject, tab_toppers, tab_search, tab_export = st.tabs([
        "🏠 Overview", "🏫 Branch-wise", "📖 Subject-wise", "🏆 Toppers", "🔍 Search", "📤 Export"
    ])

    with tab_overview:
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("#### Branch Performance Overview")
            branch_stats = student_df.groupby("branch").agg(
                students=("enrollment", "count"),
                clear_pass=("clear_pass", "sum"),
                passed=("passed", "sum"),
                avg_score=("score", "mean"),
            ).reset_index()
            branch_stats["passed_with_back"] = branch_stats["passed"] - branch_stats["clear_pass"]
            branch_stats["failed"] = branch_stats["students"] - branch_stats["passed"]
            branch_stats["pass_rate"] = (branch_stats["clear_pass"] / branch_stats["students"] * 100).round(1)
            branch_stats["avg_score"] = branch_stats["avg_score"].round(1)
            branch_stats["branch_short"] = branch_stats["branch"]

            fig = px.bar(
                branch_stats, x="branch_short", y="avg_score",
                color="pass_rate", color_continuous_scale="Viridis",
                labels={"branch_short": "Branch", "avg_score": "Avg Score", "pass_rate": "Pass %"},
                template="plotly_dark"
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=30, b=0),
                coloraxis_colorbar=dict(title="Pass %"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("#### Pass vs Fail Distribution")
            fig_pie = px.pie(
                values=[clear_pass_count, passed_with_back, fail_count],
                names=["Clear Pass", "Passed with Back", "Failed"],
                color_discrete_sequence=["#10b981", "#f59e0b", "#ef4444"],
                template="plotly_dark",
                hole=0.5,
            )
            fig_pie.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("#### Branch-wise Summary Table")
        display_bs = branch_stats[["branch", "students", "clear_pass", "passed_with_back", "failed", "pass_rate", "avg_score"]].copy()
        display_bs.columns = ["Branch", "Total", "Clear Pass", "Pass w/ Back", "Failed", "Clear Pass Rate (%)", "Avg Score"]
        st.dataframe(display_bs, use_container_width=True, hide_index=True)
        render_download_buttons(display_bs, "Branch Wise Summary")

    with tab_branch:
        selected_branch = st.selectbox("Select Branch", branches, key="branch_tab_sel")
        
        branch_students = student_df[student_df["branch"] == selected_branch].copy()

        if branch_students.empty:
            st.info("No results found for this branch.")
        else:
            b_total  = len(branch_students)
            b_passed = branch_students["passed"].sum()
            b_pct    = round(b_passed / b_total * 100, 1)
            b_avg    = round(branch_students["score"].mean(), 1)

            c1, c2, c3, c4 = st.columns(4)
            metrics = [(b_total,"Students","#6366f1"),(b_passed,"Passed","#10b981"),(f"{b_pct}%","Pass Rate","#f59e0b"),(b_avg,"Avg Score","#3b82f6")]
            for col, (v, l, color) in zip([c1,c2,c3,c4], metrics):
                col.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:{color}">{v}</div><div class="kpi-lbl">{l}</div></div>', unsafe_allow_html=True)

            st.markdown("---")

            col_hist, col_rank = st.columns(2)
            with col_hist:
                st.markdown("#### Score Distribution")
                fig_hist = px.histogram(
                    branch_students[branch_students["score"] > 0], x="score",
                    nbins=20, template="plotly_dark",
                    color_discrete_sequence=["#6366f1"]
                )
                fig_hist.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_hist, use_container_width=True)

            with col_rank:
                st.markdown("#### Top 10 Rankers")
                top10 = branch_students.nlargest(10, "percentage")[["student_name","percentage","score","grand_total","passed"]]
                top10.index = range(1, len(top10)+1)
                st.dataframe(top10.rename(columns={"student_name":"Name","percentage":"Percentage","score":"Score","grand_total":"Grand Total","passed":"Pass"}), use_container_width=True)

            st.markdown("#### Full Branch Result Sheet")
            display_b = branch_students[["enrollment","student_name","father_name","score","grand_total","status","passed"]].copy()
            display_b["Status"] = display_b.apply(lambda row: f"✅ {row['status']}" if row["passed"] else f"❌ {row['status']}", axis=1)
            display_b = display_b.drop(["status", "passed"], axis=1)
            display_b.index = range(1, len(display_b)+1)
            st.dataframe(
                display_b.rename(columns={
                    "enrollment":"Enrollment","student_name":"Name","father_name":"Father","score":"Score","grand_total":"Grand Total"
                }),
                use_container_width=True
            )
            render_download_buttons(display_b, f"Full Branch Result - {selected_branch}")
            
            st.markdown("#### Download Original BTEUP Result PDFs")
            st.markdown("Download a ZIP archive containing the exact original result PDF for every student in this branch, generated directly from the BTEUP website.")
            zip_cache_key = f"orig_zip_{selected_branch}"
            if zip_cache_key not in st.session_state:
                if st.button("📦 Generate Original PDFs ZIP (Takes 1-2 sec per student)", key="gen_orig_zip", use_container_width=True):
                    prog_bar = st.progress(0)
                    status_text = st.empty()
                    
                    import io, zipfile, base64, shutil
                    try:
                        import pdfkit
                        wk_path = shutil.which("wkhtmltopdf")
                        cfg = pdfkit.configuration(wkhtmltopdf=wk_path) if wk_path else None
                        opts = {'quiet': '', 'javascript-delay': '500'}
                        
                        zip_buffer = io.BytesIO()
                        total = len(branch_students)
                        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                            for i, (_, row_data) in enumerate(branch_students.iterrows()):
                                enroll = str(row_data["enrollment"]).strip()
                                dob = str(row_data.get("dob", "")).strip()
                                branch_clean = str(row_data.get("branch", "Result")).replace("/", "_").replace(":", "")
                                
                                status_text.text(f"Generating PDF for {enroll}... ({i+1}/{total})")
                                prog_bar.progress((i + 1) / total)
                                
                                enr_b64 = base64.b64encode(enroll.encode()).decode()
                                dob_b64 = base64.b64encode(dob.encode()).decode()
                                url = f"https://result.bteexam.com/even/main/oddresult.aspx?id={enr_b64}&id2={dob_b64}"
                                try:
                                    if cfg:
                                        pdf_data = pdfkit.from_url(url, False, options=opts, configuration=cfg)
                                    else:
                                        pdf_data = pdfkit.from_url(url, False, options=opts)
                                    if pdf_data:
                                        zf.writestr(f"{branch_clean}_{enroll}.pdf", pdf_data)
                                except Exception:
                                    pass
                        
                        status_text.empty()
                        prog_bar.empty()
                        st.session_state[zip_cache_key] = zip_buffer.getvalue()
                        st.rerun()
                    except ImportError:
                        status_text.error("pdfkit is not installed. Please add it to requirements.txt")
            else:
                st.success("Original PDFs ZIP generated successfully!")
                st.download_button(
                    "📥 Download ZIP Archive", 
                    data=st.session_state[zip_cache_key], 
                    file_name=f"Original_Results_{selected_branch.replace(' ', '_')}.zip", 
                    mime="application/zip", 
                    use_container_width=True, 
                    type="primary"
                )

            st.markdown("#### Subject Performance (this branch)")
            branch_raw = raw_df[raw_df["branch"] == selected_branch].copy()
            subj_stats = branch_raw.groupby("subject_display").agg(
                count=("marks_obtained_int","count"),
                avg=("marks_obtained_int","mean"),
                highest=("marks_obtained_int","max"),
                lowest=("marks_obtained_int","min"),
                failed=("is_pass_subject", lambda x: (~x).sum())
            ).reset_index()
            subj_stats["avg"] = subj_stats["avg"].round(1)
            
            def sort_key(s):
                s_up = s.upper()
                if any(x in s_up for x in ["SESSIONAL", "SCA", "YOGA", "STUDENT CENTRED"]):
                    return (1, s)
                return (0, s)
            
            subj_stats["sort_col"] = subj_stats["subject_display"].apply(sort_key)
            subj_stats = subj_stats.sort_values(["sort_col", "subject_display"]).drop("sort_col", axis=1).reset_index(drop=True)
            subj_stats.index += 1
            st.dataframe(subj_stats.rename(columns={
                "subject_display":"Subject","count":"Students","avg":"Avg","highest":"Highest","lowest":"Lowest","failed":"Failed"
            }), use_container_width=True)


    with tab_subject:
        col_l, col_r = st.columns([3, 1])
        with col_l:
            sel_subject = st.selectbox("Select Subject / Paper", subjects, key="subj_sel")
        with col_r:
            sel_branch_filter = st.selectbox("Branch Filter", ["All"] + branches, key="subj_branch_filter")

        subj_df = raw_df[raw_df["subject_display"] == sel_subject].copy()
        if sel_branch_filter != "All":
            subj_df = subj_df[subj_df["branch"] == sel_branch_filter]

        if subj_df.empty:
            st.info("No data for this subject/filter combination.")
        else:
            s_avg     = round(subj_df["marks_obtained_int"].mean(), 1)
            s_max     = subj_df["marks_obtained_int"].max()
            s_min     = subj_df["marks_obtained_int"].min()
            s_failed  = (~subj_df["is_pass_subject"]).sum()
            s_total   = len(subj_df)
            s_fail_pct= round(s_failed / s_total * 100, 1) if s_total else 0

            c1,c2,c3,c4,c5 = st.columns(5)
            for col,(v,l,cl) in zip([c1,c2,c3,c4],[
                (s_total,"Students","#6366f1"),(s_avg,"Average","#3b82f6"),
                (s_max,"Highest","#10b981"),(s_min,"Lowest","#f59e0b")
            ]):
                col.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:{cl}">{v}</div><div class="kpi-lbl">{l}</div></div>', unsafe_allow_html=True)
            
            c5.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:#ef4444">{s_failed}</div><div style="font-size:0.8rem;color:#ef4444;font-weight:bold;">({s_fail_pct}%)</div><div class="kpi-lbl">Failed</div></div>', unsafe_allow_html=True)

            st.markdown("---")
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("#### Score Distribution")
                fig_s = px.histogram(subj_df, x="marks_obtained_int", nbins=15,
                    color_discrete_sequence=["#8b5cf6"], template="plotly_dark",
                    labels={"marks_obtained_int":"Marks"})
                fig_s.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_s, use_container_width=True)

            with col_b:
                st.markdown("#### Per-Branch Comparison")
                branch_subj = subj_df.groupby("branch")["marks_obtained_int"].mean().round(1).reset_index()
                branch_subj.columns = ["Branch","Avg Marks"]
                fig_bcomp = px.bar(branch_subj, x="Branch", y="Avg Marks",
                    color="Avg Marks", color_continuous_scale="Plasma",
                    template="plotly_dark")
                fig_bcomp.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_bcomp, use_container_width=True)

            st.markdown("#### Top Performers in this Subject")
            top_subj = subj_df.nlargest(20, "marks_obtained_int")[["enrollment","student_name","branch","marks_obtained_int","max_marks_int","is_pass_subject"]].copy()
            top_subj["is_pass_subject"] = top_subj["is_pass_subject"].map({True:"🟢 Pass", False:"🔴 Fail"})
            top_subj.index = range(1, len(top_subj)+1)
            st.dataframe(top_subj.rename(columns={
                "enrollment":"Enrollment","student_name":"Name","branch":"Branch",
                "marks_obtained_int":"Obtained","max_marks_int":"Max Marks","is_pass_subject":"Status"
            }), use_container_width=True)

            st.markdown("#### Download Subject Results")
            d_col1, d_col2, d_col3 = st.columns(3)
            
            export_subj = subj_df[[
                "enrollment", "student_name", "father_name", "branch", "subject_display", 
                "max_marks_int", "min_marks_int", "marks_obtained_int", "is_pass_subject"
            ]].copy()
            export_subj["is_pass_subject"] = export_subj["is_pass_subject"].map({True:"PASS", False:"FAIL"})
            export_subj.rename(columns={
                "enrollment": "Enrollment", "student_name": "Student Name", "father_name": "Father's Name",
                "branch": "Branch", "subject_display": "Subject", "max_marks_int": "Max Marks",
                "min_marks_int": "Min Marks", "marks_obtained_int": "Marks Obtained", "is_pass_subject": "Status"
            }, inplace=True)

            with d_col1:
                st.download_button(
                    f"📥 Download CSV", 
                    data=export_subj.to_csv(index=False).encode("utf-8"), 
                    file_name=f"subject_{sel_subject.replace(' ','_')}.csv", 
                    mime="text/csv", use_container_width=True
                )
            with d_col2:
                st.download_button(
                    f"📥 Download Excel", 
                    data=to_excel_bytes(export_subj), 
                    file_name=f"subject_{sel_subject.replace(' ','_')}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
                )
            with d_col3:
                cache_key = f"pdf_subj_{sel_subject.replace(' ','_')}"
                if cache_key not in st.session_state:
                    if st.button(f"🚀 Prepare PDF", key=f"prep_pdf_{cache_key}", use_container_width=True):
                        with st.spinner(f"Preparing PDF for {len(export_subj)} records..."):
                            st.session_state[cache_key] = to_pdf_bytes(export_subj, title=f"Subject Result: {sel_subject}")
                        st.rerun()
                else:
                    st.download_button(
                        f"📥 Download PDF", 
                        data=st.session_state[cache_key], 
                        file_name=f"subject_{sel_subject.replace(' ','_')}.pdf", 
                        mime="application/pdf", use_container_width=True
                    )


    with tab_toppers:
        st.markdown("### 🏆 College Topper (Overall)")
        clear_students = student_df[student_df["clear_pass"] == True]
        if not clear_students.empty:
            topper = clear_students.iloc[0]
            st.markdown(f"""
            <div class="topper-card">
              <div style="display:flex;align-items:center;gap:1.5rem;">
                <div class="topper-rank">🥇</div>
                <img src="https://bteup.ac.in/PDFFILES/STUDENTIMAGES/P{topper['enrollment']}.jpg" style="width:70px;height:70px;border-radius:50%;object-fit:cover;border:2px solid #a5b4fc;">
                <div>
                  <div class="topper-name">{topper['student_name']}</div>
                  <div class="topper-score">
                    {topper['branch']} &nbsp;|&nbsp; Percentage: {topper['percentage']}% &nbsp;|&nbsp; Score: {topper['score']} &nbsp;|&nbsp;
                    Enrollment: {topper['enrollment']}
                  </div>
                  <div style="margin-top:4px;font-size:0.85rem;color:rgba(255,255,255,0.7)">{topper['grand_total']}</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🏫 Branch-wise Toppers (Top 10)")
        b_sel = st.selectbox("Select Branch for Toppers", branches, key="topper_b_sel")
        b_top = clear_students[clear_students["branch"] == b_sel].head(10)[["enrollment","student_name","percentage","score","status"]]
        if b_top.empty:
            st.info("No clear pass students found in this branch.")
        else:
            b_top.index = range(1, len(b_top)+1)
            st.dataframe(b_top.rename(columns={"enrollment":"Enrollment","student_name":"Name","percentage":"Percentage (%)","score":"Score","status":"Status"}), use_container_width=True)
            render_download_buttons(b_top, f"Branch Toppers - {b_sel}")

        st.markdown("---")
        st.markdown("### 📅 Year-wise Toppers (Top 10)")
        years = sorted([y for y in clear_students["year"].unique() if y != "Unknown Year"])
        if years:
            tabs_y = st.tabs(years)
            for i, y in enumerate(years):
                with tabs_y[i]:
                    y_top = clear_students[clear_students["year"] == y].head(10)[["enrollment","student_name","branch","percentage","score","status"]]
                    y_top.index = range(1, len(y_top)+1)
                    st.dataframe(y_top.rename(columns={"enrollment":"Enrollment","student_name":"Name","branch":"Branch","percentage":"Percentage (%)","score":"Score","status":"Status"}), use_container_width=True)
                    render_download_buttons(y_top, f"Year Toppers - {y}")

        st.markdown("---")
        st.markdown("### 📊 Overall / Filtered Top 20")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            t_branch = st.selectbox("Filter by Branch", ["All"] + branches, key="topper_branch")
        with col_t2:
            t_year = st.selectbox("Filter by Year", ["All"] + years, key="topper_year")
            
        t_df = clear_students[clear_students["score"] > 0].copy()
        if t_branch != "All":
            t_df = t_df[t_df["branch"] == t_branch]
        if t_year != "All":
            t_df = t_df[t_df["year"] == t_year]
            
        top20 = t_df.head(20)[
            ["student_name","enrollment","branch","year","percentage","score","status"]
        ].copy()
        top20.index = range(1, len(top20)+1)
        st.dataframe(top20.rename(columns={
            "student_name":"Name","enrollment":"Enrollment","branch":"Branch","year":"Year",
            "percentage":"Percentage (%)","score":"Score","status":"Status"
        }), use_container_width=True)
        render_download_buttons(top20, "Top 20 Rank List")

        st.markdown("### 📖 Subject Toppers")
        subj_toppers = raw_df[raw_df["marks_obtained_int"] > 0].sort_values("marks_obtained_int", ascending=False)
        subj_toppers = subj_toppers.groupby("subject_display").first().reset_index()
        subj_toppers = subj_toppers[["subject_display","student_name","enrollment","branch","marks_obtained_int"]].copy()
        subj_toppers = subj_toppers.sort_values("subject_display")
        st.dataframe(subj_toppers.rename(columns={
            "subject_display":"Subject","student_name":"Topper","enrollment":"Enrollment",
            "branch":"Branch","marks_obtained_int":"Marks"
        }), use_container_width=True, hide_index=True)


    with tab_search:
        st.markdown("### 🔍 Student Search")
        col_q, col_b = st.columns([3, 1])
        with col_q:
            query = st.text_input("Search by Name or Enrollment Number", placeholder="Type name or enrollment...", key="search_q")
        with col_b:
            branch_filter_s = st.selectbox("Branch", ["All"] + branches, key="search_branch")

        filtered = student_df.copy()
        if query:
            mask = (
                filtered["student_name"].str.contains(query, case=False, na=False) |
                filtered["enrollment"].str.contains(query, case=False, na=False)
            )
            filtered = filtered[mask]
        if branch_filter_s != "All":
            filtered = filtered[filtered["branch"] == branch_filter_s]

        st.markdown(f"**{len(filtered)} students found**")
        display_filtered = filtered[["enrollment","student_name","father_name","branch","score","percentage","status","passed"]].copy()
        display_filtered["Passed"] = display_filtered["passed"].map({True:"✅ Pass", False:"❌ Fail"})
        display_filtered = display_filtered.drop("passed", axis=1)
        display_filtered.index = range(1, len(display_filtered)+1)
        st.dataframe(display_filtered.rename(columns={
            "enrollment":"Enrollment","student_name":"Name","father_name":"Father","branch":"Branch",
            "score":"Score","percentage":"Percentage","status":"Status"
        }), use_container_width=True)

        # Click to expand a single student's subject marks
        if not filtered.empty:
            st.markdown("#### View Subject-wise Marks for a Student")
            sel_enroll = st.selectbox(
                "Select student", 
                options=filtered["enrollment"].tolist(),
                format_func=lambda e: f"{e} — {filtered[filtered['enrollment']==e]['student_name'].values[0]}",
                key="student_detail_sel"
            )
            student_marks = raw_df[raw_df["enrollment"] == sel_enroll][
                ["paper_code","paper_name","max_marks","min_marks","marks_obtained","is_pass_subject"]
            ].copy()
            student_marks["Result"] = student_marks["is_pass_subject"].map({True:"✅","False":"❌"})
            student_marks = student_marks.drop("is_pass_subject", axis=1)
            student_marks.index = range(1, len(student_marks)+1)
            
            c_p1, c_p2 = st.columns([1, 4])
            with c_p1:
                st.image(f"https://bteup.ac.in/PDFFILES/STUDENTIMAGES/P{sel_enroll}.jpg", use_container_width=True)
            with c_p2:
                st.dataframe(student_marks.rename(columns={
                    "paper_code":"Code","paper_name":"Subject","max_marks":"Max","min_marks":"Min","marks_obtained":"Obtained"
                }), use_container_width=True)
                render_download_buttons(student_marks, f"Marks_{sel_enroll}")
                
        st.markdown("---")
        st.markdown("### ⚠️ Exceptions & Absentees (AA/MW)")
        st.markdown("Students who were Absent (AA) or have Marks Waiting (MW) for any subject.")
        
        exceptions = raw_df[raw_df["marks_obtained"].astype(str).str.strip().str.upper().isin(["AA", "MW"])].copy()
        if not exceptions.empty:
            exceptions_display = exceptions[["enrollment", "student_name", "branch", "subject_display", "marks_obtained"]].copy()
            exceptions_display.index = range(1, len(exceptions_display)+1)
            st.dataframe(exceptions_display.rename(columns={
                "enrollment": "Enrollment", "student_name": "Name", "branch": "Branch",
                "subject_display": "Subject", "marks_obtained": "Status (AA/MW)"
            }), use_container_width=True)
            render_download_buttons(exceptions_display, "Absentees_and_Exceptions")
        else:
            st.success("No students found with AA or MW status!")

    with tab_export:
        st.markdown("### 📤 Export Data")
        st.markdown("Download result data in various formats.")

        col_e1, col_e2 = st.columns(2)

        with col_e1:
            st.markdown("#### All Results (raw)")
            all_raw = raw_df.drop(columns=["id","fetched_at"], errors="ignore")
            csv_bytes = all_raw.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download All Results CSV", data=csv_bytes, file_name="bteup_all_results.csv", mime="text/csv", use_container_width=True)
            xl_bytes = to_excel_bytes(all_raw)
            st.download_button("⬇️ Download All Results Excel", data=xl_bytes, file_name="bteup_all_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        with col_e2:
            st.markdown("#### Student Summary")
            summary_export = student_df[["enrollment","student_name","father_name","branch","score","grand_total","passed"]].copy()
            summary_export["passed"] = summary_export["passed"].map({True:"PASS",False:"FAIL"})
            csv2 = summary_export.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Student Summary CSV", data=csv2, file_name="bteup_student_summary.csv", mime="text/csv", use_container_width=True)
            xl2 = to_excel_bytes(summary_export)
            st.download_button("⬇️ Download Student Summary Excel", data=xl2, file_name="bteup_student_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        st.markdown("---")
        st.markdown("#### Branch-wise Export")
        exp_branch = st.selectbox("Select Branch", branches, key="export_branch")
        exp_df = raw_df[raw_df["branch"] == exp_branch].drop(columns=["id","fetched_at"], errors="ignore")
        st.markdown(f"**{len(exp_df)} rows** in **{exp_branch}**")
        xl_branch = to_excel_bytes(exp_df)
        st.download_button(
            f"⬇️ Download {exp_branch} Results", data=xl_branch,
            file_name=f"results_{exp_branch[:20].replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.markdown("---")
        st.markdown("#### Top 20 Rank List")
        rank_df = student_df[student_df["score"] > 0].head(20)[
            ["student_name","enrollment","branch","score","grand_total"]
        ].copy()
        rank_df.index = range(1, len(rank_df)+1)
        rank_df.index.name = "Rank"
        xl_rank = to_excel_bytes(rank_df.reset_index())
        st.download_button("⬇️ Download Rank List Excel", data=xl_rank, file_name="bteup_toppers.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

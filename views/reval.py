"""
views/reval.py  —  BTEUP REVAL Result Downloader View
Enables downloading and analyzing BTEUP Re-Evaluation / Scrutiny results.
"""
import streamlit as st
import pandas as pd
import time
import base64
import requests
import urllib3

from core.db import (
    get_all_students, get_branches, get_student_count, get_all_results,
    insert_reval_results, get_all_reval_results, get_already_checked_reval_enrollments,
    get_reval_stats, clear_reval_results, get_failed_students
)
from core.reval_fetcher import fetch_single_reval, fetch_reval_batch
from views.analytics import to_excel_bytes, html_to_pdf_bytes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def render():
    st.markdown('<div class="section-header">🔍 REVAL Result Downloader</div>', unsafe_allow_html=True)
    st.markdown(
        "Extract and analyze official **BTEUP Re-Evaluation / Scrutiny results** directly from the portal. "
        "You can check all students, filter by failed students, or enter specific enrollment numbers."
    )

    current_inst = st.session_state.get('current_institute')
    stats = get_reval_stats(current_inst)
    student_count = get_student_count(current_inst)

    # ── Top KPI Stat Chips ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-chip"><div class="val">{student_count}</div><div class="lbl">Students in DB</div></div>
      <div class="stat-chip"><div class="val" style="color:#6366f1">{stats['total_checked']}</div><div class="lbl">Reval Checked</div></div>
      <div class="stat-chip"><div class="val" style="color:#10b981">{stats['found']}</div><div class="lbl">Reval Found</div></div>
      <div class="stat-chip"><div class="val" style="color:#f59e0b">{stats['not_found']}</div><div class="lbl">No Reval Record</div></div>
      <div class="stat-chip"><div class="val" style="color:#0ea5e9">{stats['subjects_found']}</div><div class="lbl">Subject Changes</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "🌐 Batch Extraction (All / By Branch)",
        "🎯 Specific Enrollment Lookup",
        "📊 View & Export Reval Results"
    ])

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 1: BATCH EXTRACTION
    # ══════════════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 🌐 Batch REVAL Result Extraction")
        st.markdown("Select students from your database to query against the BTEUP Re-Evaluation portal.")

        col_scope, col_opts = st.columns([2, 1])

        with col_scope:
            fetch_scope = st.radio(
                "Select Students Scope",
                ["All Students in DB", "Only Students Who Failed / Had Back Papers", "By Specific Branch"],
                horizontal=False
            )

            target_students_df = pd.DataFrame()

            if fetch_scope == "All Students in DB":
                target_students_df = get_all_students(current_inst)
            elif fetch_scope == "Only Students Who Failed / Had Back Papers":
                target_students_df = get_failed_students(current_inst)
                if target_students_df.empty:
                    st.info("No failed / back paper students found in the fetched results database.")
                else:
                    st.success(f"Found **{len(target_students_df)}** students with back / failed subjects.")
            elif fetch_scope == "By Specific Branch":
                branches = get_branches(current_inst)
                selected_b = st.multiselect("Select Branch(es)", branches, default=branches[:1] if branches else [])
                if selected_b:
                    all_dfs = [get_all_students(current_inst)]
                    full_df = pd.concat(all_dfs) if all_dfs else pd.DataFrame()
                    if not full_df.empty:
                        target_students_df = full_df[full_df["branch"].isin(selected_b)]

        with col_opts:
            st.markdown("##### Extraction Options")
            skip_checked = st.checkbox("⚡ Skip already checked", value=True, help="Skip enrollments that already have a record in reval_results table.")
            force_refetch = st.checkbox("🔄 Force Refetch", value=False, help="Re-query even if already checked.")
            max_workers = st.slider("Concurrent Workers", min_value=1, max_value=10, value=5, help="Speed up extraction with multi-threaded downloads.")

        if not target_students_df.empty:
            already_checked = get_already_checked_reval_enrollments(current_inst)
            if skip_checked and not force_refetch:
                eligible_df = target_students_df[~target_students_df["enrollment"].isin(already_checked)]
            else:
                eligible_df = target_students_df

            st.info(f"📋 Ready to extract REVAL results for **{len(eligible_df)}** students (out of {len(target_students_df)} in selected group).")

            if len(eligible_df) > 0:
                if st.button("🚀 Start Batch REVAL Extraction", type="primary", use_container_width=True):
                    student_list = eligible_df[["enrollment", "dob", "name", "branch", "institute", "rollno"]].to_dict("records")
                    
                    prog_bar = st.progress(0)
                    status_placeholder = st.empty()
                    metrics_placeholder = st.empty()

                    start_time = time.time()

                    def on_progress(completed, total, enr, status, rows_found):
                        pct = completed / total
                        prog_bar.progress(pct)
                        status_placeholder.text(f"Extracting [{completed}/{total}]: {enr} -> {status.upper()} ({rows_found} subject rows)")

                    with st.spinner("Extracting REVAL results from BTEUP portal..."):
                        all_rows, fetch_stats = fetch_reval_batch(
                            student_list,
                            skip_enrollments=set() if force_refetch else already_checked,
                            progress_callback=on_progress,
                            max_workers=max_workers
                        )
                        
                        if all_rows:
                            insert_reval_results(all_rows)

                    elapsed = round(time.time() - start_time, 1)
                    prog_bar.progress(1.0)
                    status_placeholder.empty()

                    st.success(
                        f"✅ Finished REVAL extraction in **{elapsed}s**! "
                        f"Queried: {fetch_stats['fetched']}, "
                        f"Found Reval: **{fetch_stats['found']}**, "
                        f"No Record: **{fetch_stats['not_found']}**, "
                        f"Errors: **{fetch_stats['error']}**."
                    )
                    st.rerun()
            else:
                st.success("🎉 All students in this group have already been checked for REVAL results!")
        else:
            st.warning("⚠️ No students found in the selected scope.")

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 2: SPECIFIC ENROLLMENT LOOKUP
    # ══════════════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 🎯 Single or Custom Enrollment Lookup")
        st.markdown("Check REVAL results for specific enrollment numbers. If the student exists in the database, their DOB will be auto-filled.")

        lookup_type = st.radio("Lookup Method", ["Single Enrollment", "Multiple Enrollments (Paste List)"], horizontal=True)

        if lookup_type == "Single Enrollment":
            c_enr, c_dob, c_btn = st.columns([2, 1, 1])
            with c_enr:
                single_enr = st.text_input("Enrollment Number", placeholder="e.g. E25273735500035").strip().upper()
            
            # Auto-fill DOB if in database
            all_stu = get_all_students(current_inst)
            matched_dob = ""
            matched_name = ""
            matched_branch = ""
            if single_enr and not all_stu.empty:
                m = all_stu[all_stu["enrollment"].str.upper() == single_enr]
                if not m.empty:
                    matched_dob = m.iloc[0]["dob"] or ""
                    matched_name = m.iloc[0]["name"] or ""
                    matched_branch = m.iloc[0]["branch"] or ""
                    st.caption(f"👤 Found student in DB: **{matched_name}** | {matched_branch}")

            with c_dob:
                single_dob = st.text_input("Date of Birth (DD/MM/YYYY)", value=matched_dob, placeholder="16/03/2010").strip()

            with c_btn:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                fetch_single_btn = st.button("🔍 Check Reval", type="primary", use_container_width=True)

            if fetch_single_btn:
                if not single_enr or not single_dob:
                    st.error("Please provide both Enrollment Number and Date of Birth.")
                else:
                    with st.spinner(f"Querying REVAL portal for {single_enr}..."):
                        rows, status = fetch_single_reval(single_enr, single_dob)
                        for r in rows:
                            if matched_name:
                                r["student_name"] = matched_name
                            if matched_branch:
                                r["branch"] = matched_branch
                            if current_inst:
                                r["institute"] = current_inst
                        insert_reval_results(rows)

                    if status == "ok":
                        st.success(f"✅ REVAL Result Found for **{single_enr}**! ({len(rows)} subject rows)")
                        df_res = pd.DataFrame(rows)[["qp_no", "paper_name", "reval_marks", "remarks"]]
                        df_res.columns = ["QPNO", "Paper Name", "Re-Evaluation Marks", "Remarks"]
                        df_res.index = range(1, len(df_res) + 1)
                        st.dataframe(df_res, use_container_width=True)
                    elif status == "not_found":
                        st.warning(f"⚠️ No REVAL Record Found for **{single_enr}** (Student did not apply for reval or result not declared). Saved status as NOT_FOUND.")
                    else:
                        st.error(f"❌ Error querying REVAL portal: {rows[0].get('remarks', 'Unknown error')}")

        else:
            st.markdown("##### Paste Multiple Enrollments")
            st.caption("Paste a list of enrollment numbers (one per line or comma-separated). DOBs will be looked up from the database.")
            enr_text = st.text_area("Enrollment Numbers", placeholder="E25273735500035\nE25221535200012\nE24273732200014", height=120)

            if st.button("🚀 Fetch Reval for Entered Enrollments", type="primary"):
                import re
                raw_enrs = [e.strip().upper() for e in re.split(r'[\r\n,]+', enr_text) if e.strip()]
                raw_enrs = list(dict.fromkeys(raw_enrs))

                if not raw_enrs:
                    st.error("Please enter at least one enrollment number.")
                else:
                    all_stu = get_all_students(current_inst)
                    stu_map = {r["enrollment"].upper(): r for _, r in all_stu.iterrows()} if not all_stu.empty else {}

                    students_to_query = []
                    missing_dobs = []
                    for enr in raw_enrs:
                        if enr in stu_map and stu_map[enr].get("dob"):
                            s = stu_map[enr]
                            students_to_query.append({
                                "enrollment": enr,
                                "dob": s["dob"],
                                "name": s.get("name", ""),
                                "branch": s.get("branch", ""),
                                "institute": s.get("institute", "")
                            })
                        else:
                            missing_dobs.append(enr)

                    if missing_dobs:
                        st.warning(f"⚠️ {len(missing_dobs)} enrollment(s) not found in DB with DOB: {', '.join(missing_dobs[:5])}...")

                    if students_to_query:
                        pbar = st.progress(0)
                        status_t = st.empty()

                        def prog(comp, tot, enr, st_code, r_count):
                            pbar.progress(comp / tot)
                            status_t.text(f"Querying [{comp}/{tot}]: {enr} -> {st_code.upper()}")

                        with st.spinner(f"Extracting REVAL results for {len(students_to_query)} students..."):
                            rows, stats_res = fetch_reval_batch(students_to_query, progress_callback=prog, max_workers=5)
                            if rows:
                                insert_reval_results(rows)

                        pbar.progress(1.0)
                        status_t.empty()
                        st.success(f"✅ Finished! Found Reval: {stats_res['found']}, Not Found: {stats_res['not_found']}.")
                        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 3: VIEW & EXPORT REVAL RESULTS
    # ══════════════════════════════════════════════════════════════════════════════
    with tab3:
        top_c1, top_c2 = st.columns([3, 1])
        with top_c1:
            st.markdown("### 📊 Stored REVAL Results")
        with top_c2:
            if st.button("📊 Open in Analytics Dashboard", type="primary", use_container_width=True):
                st.session_state.apply_reval_analytics = True
                st.session_state.page = "analytics"
                st.rerun()

        reval_df = get_all_reval_results(current_inst)
        if reval_df.empty:
            reval_df = get_all_reval_results(None)

        if reval_df.empty:
            st.info("No REVAL results have been extracted yet. Use the tabs above to extract results!")
            return

        # ── Filters Bar ───────────────────────────────────────────────────────────────
        f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
        with f_col1:
            status_filter = st.selectbox("Filter Status", ["All Records", "Only Found (with Reval Marks)", "Not Applied / No Record"])
        with f_col2:
            branch_list = ["All Branches"] + sorted([b for b in reval_df["branch"].dropna().unique() if b])
            selected_branch = st.selectbox("Filter Branch", branch_list)
        with f_col3:
            search_query = st.text_input("Search Student, Enrollment, or Subject", placeholder="Type name, enrollment or paper...").strip()

        # Apply filters
        filtered_df = reval_df.copy()
        if status_filter == "Only Found (with Reval Marks)":
            filtered_df = filtered_df[filtered_df["status"] == "FOUND"]
        elif status_filter == "Not Applied / No Record":
            filtered_df = filtered_df[filtered_df["status"] != "FOUND"]

        if selected_branch != "All Branches":
            filtered_df = filtered_df[filtered_df["branch"] == selected_branch]

        if search_query:
            mask = (
                filtered_df["student_name"].fillna("").str.contains(search_query, case=False) |
                filtered_df["enrollment"].fillna("").str.contains(search_query, case=False) |
                filtered_df["paper_name"].fillna("").str.contains(search_query, case=False) |
                filtered_df["qp_no"].fillna("").str.contains(search_query, case=False)
            )
            filtered_df = filtered_df[mask]

        # ── Match with Original Marks (if available in results table) ────────────────
        all_results_df = get_all_results(current_inst)
        if not all_results_df.empty:
            orig_map = {}
            for _, r in all_results_df.iterrows():
                enr = str(r["enrollment"]).strip().upper()
                p_code = str(r.get("paper_code", "")).strip().upper()
                p_name = str(r.get("paper_name", "")).strip().upper()
                mo = str(r.get("marks_obtained", "")).strip()
                mx = str(r.get("max_marks", "")).strip()
                try:
                    mx_int = int(float(mx))
                except Exception:
                    mx_int = 0
                # Filter to theory papers
                if mx_int >= 50 or not p_code.endswith(('21', '22', '23', '24', '25')):
                    orig_map[(enr, p_name)] = mo
                    orig_map[(enr, p_name.replace('-', ' - '))] = mo
                    orig_map[(enr, p_name.replace(' - ', '-'))] = mo

            def get_orig(row):
                enr = str(row["enrollment"]).strip().upper()
                pn = str(row["paper_name"]).strip().upper()
                return orig_map.get((enr, pn), "-")

            filtered_df["original_marks"] = filtered_df.apply(get_orig, axis=1)

            def get_diff(row):
                if row["status"] != "FOUND":
                    return "-"
                try:
                    orig = int(row["original_marks"])
                    rev = int(row["reval_marks"])
                    diff = rev - orig
                    if diff > 0:
                        return f"📈 +{diff}"
                    elif diff < 0:
                        return f"📉 {diff}"
                    else:
                        return "➖ 0"
                except Exception:
                    return "-"

            filtered_df["diff"] = filtered_df.apply(get_diff, axis=1)

        # ── Prepare display table ───────────────────────────────────────────────────
        display_cols = ["enrollment", "roll_no", "student_name", "branch", "qp_no", "paper_name"]
        if "original_marks" in filtered_df.columns:
            display_cols.extend(["original_marks", "reval_marks", "diff", "remarks", "status"])
            col_rename = {
                "enrollment": "Enrollment",
                "roll_no": "Roll No",
                "student_name": "Student Name",
                "branch": "Branch",
                "qp_no": "QPNO",
                "paper_name": "Paper Name",
                "original_marks": "Original Marks",
                "reval_marks": "Reval Marks",
                "diff": "Change",
                "remarks": "Remarks",
                "status": "Status"
            }
        else:
            display_cols.extend(["reval_marks", "remarks", "status"])
            col_rename = {
                "enrollment": "Enrollment",
                "roll_no": "Roll No",
                "student_name": "Student Name",
                "branch": "Branch",
                "qp_no": "QPNO",
                "paper_name": "Paper Name",
                "reval_marks": "Reval Marks",
                "remarks": "Remarks",
                "status": "Status"
            }

        table_to_show = filtered_df[display_cols].copy()
        table_to_show.index = range(1, len(table_to_show) + 1)
        table_to_show = table_to_show.rename(columns=col_rename)

        st.markdown(f"**Showing {len(table_to_show)} Records**")
        st.dataframe(table_to_show, use_container_width=True)

        # ── Export Buttons ──────────────────────────────────────────────────────────
        st.markdown("#### 📥 Export Reval Results")
        exp_c1, exp_c2, exp_c3 = st.columns(3)

        with exp_c1:
            xl_data = to_excel_bytes(table_to_show)
            st.download_button(
                "📊 Download as Excel (.xlsx)",
                data=xl_data,
                file_name="BTEUP_REVAL_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with exp_c2:
            csv_data = table_to_show.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📄 Download as CSV (.csv)",
                data=csv_data,
                file_name="BTEUP_REVAL_Results.csv",
                mime="text/csv",
                use_container_width=True
            )

        with exp_c3:
            found_students = filtered_df[filtered_df["status"] == "FOUND"]
            unique_found_enrs = found_students[["enrollment", "dob", "branch"]].drop_duplicates("enrollment")
            
            if st.button("📦 Generate Official PDFs ZIP", use_container_width=True, help="Downloads the exact original BTEUP REVAL web result PDF for each student who had a reval record."):
                if unique_found_enrs.empty:
                    st.warning("No students with FOUND reval status in the current filter.")
                else:
                    import io, zipfile
                    zip_buf = io.BytesIO()
                    p_bar = st.progress(0)
                    s_txt = st.empty()
                    total = len(unique_found_enrs)

                    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for i, (_, row_data) in enumerate(unique_found_enrs.iterrows()):
                            enr = str(row_data["enrollment"]).strip()
                            dob = str(row_data.get("dob", "")).strip()
                            b_clean = str(row_data.get("branch", "Reval")).replace("/", "_").replace(":", "")

                            s_txt.text(f"Rendering Reval PDF for {enr}... ({i+1}/{total})")
                            p_bar.progress((i + 1) / total)

                            enr_b64 = base64.b64encode(enr.encode()).decode()
                            dob_b64 = base64.b64encode(dob.encode()).decode()
                            url = f"https://result.bteexam.com/even/REVAL/REVAL_RollNo.aspx?id={enr_b64}&id2={dob_b64}"

                            try:
                                resp = requests.get(url, verify=False, timeout=15)
                                if resp.status_code == 200:
                                    html_text = resp.text
                                    css_injection = "<style>@page { size: A4 portrait; margin: 10mm; } table { width: 100% !important; } body { font-size: 12px; }</style>"
                                    if "</head>" in html_text:
                                        html_text = html_text.replace("</head>", f"{css_injection}</head>")
                                    else:
                                        html_text = css_injection + html_text

                                    pdf_data = html_to_pdf_bytes(html_text)
                                    if pdf_data:
                                        zf.writestr(f"REVAL_{b_clean}_{enr}.pdf", pdf_data)
                            except Exception:
                                pass

                    s_txt.empty()
                    p_bar.empty()
                    st.session_state["reval_pdf_zip"] = zip_buf.getvalue()
                    st.rerun()

            if "reval_pdf_zip" in st.session_state:
                st.download_button(
                    "📥 Click to Download REVAL PDFs ZIP",
                    data=st.session_state["reval_pdf_zip"],
                    file_name="BTEUP_REVAL_Official_PDFs.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )

        st.markdown("---")
        with st.expander("🗑️ Clear REVAL Data", expanded=False):
            st.warning("⚠️ This will remove all fetched REVAL records for the selected institute from the database.")
            if st.button("Delete REVAL Records", type="secondary"):
                clear_reval_results(current_inst)
                st.success("Reval results cleared successfully!")
                st.rerun()

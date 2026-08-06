import streamlit as st
import pandas as pd
from core.db import (
    get_branches, get_students_for_branch, get_already_fetched_enrollments,
    insert_results, get_student_count, get_result_count, get_semesters_for_branch,
    clear_results, get_all_students
)
from core.fetcher import fetch_branch_results

def render():
    st.markdown('<div class="section-header">🌐 Fetch Results from BTEUP Portal</div>', unsafe_allow_html=True)
    st.markdown("Select branches/semesters or search for individual students to fetch results directly from the BTEUP portal.")

    current_inst = st.session_state.get('current_institute')
    student_count = get_student_count(current_inst)
    result_count  = get_result_count(current_inst)

    if student_count == 0:
        st.warning("⚠️ No students loaded yet for the selected institute. Please go to **📋 Nominal** page first and upload your nominal register.")
        return

    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-chip"><div class="val">{student_count}</div><div class="lbl">Students in DB</div></div>
      <div class="stat-chip"><div class="val">{result_count}</div><div class="lbl">Results Fetched</div></div>
      <div class="stat-chip"><div class="val">{student_count - result_count}</div><div class="lbl">Remaining</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    
    fetch_mode = st.radio("Fetch Mode", ["By Branch / Semester", "Individual Student"], horizontal=True)
    
    students_to_fetch = []
    
    if fetch_mode == "By Branch / Semester":
        branches = get_branches(current_inst)

        st.markdown("### Select Branches and Semesters to Fetch")

        col1, col2 = st.columns([2, 1])
        with col1:
            selected_branches = st.multiselect(
                "Branches", branches, default=[],
                help="Select one or more branches to fetch results for"
            )
            
            branch_semesters = {}
            if selected_branches:
                st.markdown("##### Select Semesters")
                for b in selected_branches:
                    sems = get_semesters_for_branch(b, current_inst)
                    branch_semesters[b] = st.multiselect(f"Semesters for {b[:40]}...", sorted(list(sems)), default=list(sems), key=f"sem_{b}")
                
        with col2:
            skip_already_fetched = st.checkbox("⚡ Skip already fetched", value=True,
                help="Skip enrollment numbers that already have results in the database")
            
            force_refetch = st.checkbox("🔄 Re-fetch all (clear & refetch)", value=False,
                help="Clear existing results for selected branches and fetch fresh")

        if selected_branches:
            st.markdown("---")
            all_students = []
            for b in selected_branches:
                for s in branch_semesters[b]:
                    df_s = get_students_for_branch(b, s, current_inst)
                    all_students.append(df_s)
            
            if all_students:
                df = pd.concat(all_students).drop_duplicates(subset=["enrollment"])
            else:
                df = pd.DataFrame()
            
            already_fetched = get_already_fetched_enrollments(current_inst)
            
            if not df.empty and skip_already_fetched and not force_refetch:
                df = df[~df["enrollment"].isin(already_fetched)]
                
            st.info(f"Ready to fetch **{len(df)}** students from **{len(selected_branches)}** branches.")
            if not df.empty:
                students_to_fetch = [{"enrollment": r["enrollment"], "dob": r["dob"]} for _, r in df.iterrows()]
            
    else:
        st.markdown("### Search Individual Student")
        all_df = get_all_students(current_inst)
        search_q = st.text_input("Search by Name or Enrollment")
        
        if search_q:
            mask = (
                all_df["name"].str.contains(search_q, case=False, na=False) |
                all_df["enrollment"].str.contains(search_q, case=False, na=False)
            )
            filtered = all_df[mask]
            
            if not filtered.empty:
                st.dataframe(filtered[["enrollment", "name", "branch", "semester"]], hide_index=True)
                sel_enroll = st.selectbox("Select Student to Fetch", filtered["enrollment"].tolist(), 
                                        format_func=lambda e: f"{e} - {filtered[filtered['enrollment']==e]['name'].values[0]}")
                if sel_enroll:
                    row = filtered[filtered["enrollment"] == sel_enroll].iloc[0]
                    students_to_fetch = [{"enrollment": row["enrollment"], "dob": row["dob"]}]
            else:
                st.warning("No students found.")
        skip_already_fetched = False
        force_refetch = False

    st.markdown("---")

    # ── Fetch button ──────────────────────────────────────────────────────────────
    if st.button("🚀 Start Fetching Results", use_container_width=True, disabled=len(students_to_fetch)==0):
        if force_refetch and fetch_mode == "By Branch / Semester":
            clear_results()
            already_fetched = set()

        skip_set = get_already_fetched_enrollments() if (skip_already_fetched and not force_refetch) else set()

        st.markdown("### Fetching Results...")

        all_collected = []
        
        progress_bar = st.progress(0, text="Starting fetch...")
        status_box = st.empty()
        stats_box  = st.empty()

        branch_stats = {"ok": 0, "not_found": 0, "skipped": 0, "error": 0}
        log_lines = []

        def progress_cb(current, total, enroll, status):
            pct = current / total
            progress_bar.progress(pct, text=f"{enroll} — {status}")
            branch_stats[status if status in branch_stats else "error"] += 1
            log_lines.append(f"[{current}/{total}] {enroll} → {status}")
            stats_box.markdown(
                f"✅ **{branch_stats['ok']}** fetched | "
                f"⚠️ **{branch_stats['not_found']}** not found | "
                f"⏭️ **{branch_stats['skipped']}** skipped | "
                f"❌ **{branch_stats['error']}** errors"
            )

        rows, final_stats = fetch_branch_results(students_to_fetch, skip_enrollments=skip_set, progress_callback=progress_cb)

        if rows:
            insert_results(rows)
            all_collected.extend(rows)

        progress_bar.progress(1.0, text="✅ Done!")
        
        with st.expander("📋 Fetch log"):
            st.code("\n".join(log_lines[-30:]))

        st.success(f"🎉 Fetching complete! Saved **{len(all_collected)}** subject-level result rows to database.")
        st.session_state.page = "analytics"
        st.rerun()

    # ── Import existing CSV ───────────────────────────────────────────────────────
    with st.expander("📂 Import from existing CSV (instead of fetching)"):
        st.markdown("If you already have result CSVs (e.g., from `getMarks.py`), import them directly.")
        csv_file = st.file_uploader("Upload result CSV", type=["csv"], key="import_csv")
        if csv_file:
            try:
                df_import = pd.read_csv(csv_file)
                expected_cols = {"enroll", "dob", "Inst", "Std name", "Fath name", "Branch",
                                 "Roll nos", "Grand Total", "Paper Code", "Paper Name",
                                 "Max Marks", "Min Marks", "Marks Obtained"}
                if not expected_cols.issubset(set(df_import.columns)):
                    st.error(f"CSV missing expected columns. Found: {list(df_import.columns)}")
                else:
                    rows = []
                    for _, row in df_import.iterrows():
                        rows.append({
                            "enrollment": str(row["enroll"]).strip(),
                            "dob": str(row["dob"]).strip(),
                            "institute": str(row.get("Inst", "")).strip(),
                            "student_name": str(row.get("Std name", "")).strip(),
                            "father_name": str(row.get("Fath name", "")).strip(),
                            "branch": str(row.get("Branch", "")).strip(),
                            "roll_nos": str(row.get("Roll nos", "")).strip(),
                            "grand_total": str(row.get("Grand Total", "")).strip(),
                            "paper_code": str(row.get("Paper Code", "")).strip(),
                            "paper_name": str(row.get("Paper Name", "")).strip(),
                            "max_marks": str(row.get("Max Marks", "")).strip(),
                            "min_marks": str(row.get("Min Marks", "")).strip(),
                            "marks_obtained": str(row.get("Marks Obtained", "")).strip(),
                        })
                    if st.button("💾 Import into Database", key="do_import"):
                        insert_results(rows)
                        st.success(f"✅ Imported {len(rows)} rows from {csv_file.name}!")
                        st.session_state.page = "analytics"
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

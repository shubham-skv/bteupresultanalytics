import streamlit as st
import pandas as pd
from core.nominal import parse_excel, parse_pdf
from core.db import upsert_students, get_all_students, get_branches, clear_students, get_student_count

def render():
    st.markdown('<div class="section-header">📋 Nominal Register</div>', unsafe_allow_html=True)
    st.markdown("Upload the NOMINAL register as **Excel (.xlsx)** or **PDF** to extract student data.")

    # ── Current DB status ─────────────────────────────────────────────────────────
    student_count = get_student_count()
    if student_count > 0:
        branches = get_branches()
        st.success(f"✅ Database has **{student_count}** students across **{len(branches)}** branches.")
        branch_html = "".join(f'<span class="branch-chip">{b}</span>' for b in branches)
        st.markdown(f'<div class="info-box">{branch_html}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Upload section ────────────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["📊 Upload Excel", "📄 Upload PDF"])

    with tab1:
        st.markdown("#### Upload NOMINAL.xlsx")
        st.markdown("Each **sheet name** should follow the format: `2 sem ce`, `4 sem cse`, `6 sem ee`, etc.")
        
        excel_file = st.file_uploader(
            "Choose NOMINAL.xlsx", type=["xlsx", "xls"], key="excel_upload",
            help="The standard BTEUP nominal register Excel file."
        )
        
        if excel_file:
            with st.spinner("Parsing Excel file..."):
                try:
                    students = parse_excel(excel_file, source_label=excel_file.name)
                    st.success(f"✅ Found **{len(students)}** students in **{excel_file.name}**")
                    
                    if students:
                        preview_df = pd.DataFrame(students)
                        branch_summary = preview_df.groupby(["branch", "semester"]).size().reset_index(name="count")
                        st.markdown("**Branch / Semester Breakdown:**")
                        st.dataframe(branch_summary, use_container_width=True, hide_index=True)
                        
                        with st.expander("Preview student records"):
                            st.dataframe(
                                preview_df[["enrollment", "name", "father_name", "dob", "branch", "semester"]],
                                use_container_width=True, hide_index=True
                            )
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Save to Database", key="save_excel", use_container_width=True):
                                n = upsert_students(students)
                                st.success(f"✅ Saved {n} students to database!")
                                st.session_state.page = "fetch"
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Clear DB & Save Fresh", key="clear_excel", use_container_width=True):
                                clear_students()
                                n = upsert_students(students)
                                st.success(f"✅ Cleared old data and saved {n} fresh students!")
                                st.session_state.page = "fetch"
                                st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to parse Excel: {e}")

    with tab2:
        st.markdown("#### Upload Nominal Register PDF")
        st.markdown("The PDF must contain student tables with columns: Enrollment No, Name, Father's Name, Date of Birth.")
        
        pdf_file = st.file_uploader(
            "Choose PDF", type=["pdf"], key="pdf_upload",
            help="Nominal register exported as PDF."
        )
        
        if pdf_file:
            with st.spinner("Extracting records from PDF (using advanced regex)..."):
                try:
                    students = parse_pdf(pdf_file, source_label=pdf_file.name)
                    if not students:
                        st.warning("⚠️ Could not extract any student records. Make sure the PDF contains valid enrollment numbers and DOBs.")
                    else:
                        st.success(f"✅ Found **{len(students)}** students in **{pdf_file.name}**")
                        preview_df = pd.DataFrame(students)
                        
                        branch_summary = preview_df.groupby(["branch", "semester"]).size().reset_index(name="count")
                        st.markdown("**Branch / Semester Breakdown:**")
                        st.dataframe(branch_summary, use_container_width=True, hide_index=True)
                        
                        with st.expander("Preview student records"):
                            st.dataframe(
                                preview_df[["enrollment", "name", "father_name", "dob", "branch", "semester"]],
                                use_container_width=True, hide_index=True
                            )
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Save to Database", key="save_pdf", use_container_width=True):
                                n = upsert_students(students)
                                st.success(f"✅ Saved {n} students to database!")
                                st.session_state.page = "fetch"
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Clear DB & Save Fresh", key="clear_pdf", use_container_width=True):
                                clear_students()
                                n = upsert_students(students)
                                st.success(f"✅ Cleared old data and saved {n} fresh students!")
                                st.session_state.page = "fetch"
                                st.rerun()
                except ImportError:
                    st.error("❌ `pdfplumber` is not installed. Run: `pip install pdfplumber`")
                except Exception as e:
                    st.error(f"❌ Failed to parse PDF: {e}")

    st.markdown("---")

    # ── View current students ─────────────────────────────────────────────────────
    if get_student_count() > 0:
        st.markdown("### 👥 Students in Database")
        
        all_students = get_all_students()
        branches = sorted(all_students["branch"].unique().tolist())
        
        selected_branch = st.selectbox("Filter by Branch", ["All"] + branches, key="view_branch")
        
        if selected_branch != "All":
            view_df = all_students[all_students["branch"] == selected_branch]
        else:
            view_df = all_students
        
        semesters = sorted(view_df["semester"].unique().tolist())
        selected_sem = st.selectbox("Filter by Semester", ["All"] + semesters, key="view_sem")
        if selected_sem != "All":
            view_df = view_df[view_df["semester"] == selected_sem]
        
        st.markdown(f"Showing **{len(view_df)}** students")
        st.dataframe(
            view_df[["enrollment", "name", "father_name", "dob", "branch", "semester", "rollno"]].reset_index(drop=True),
            use_container_width=True, hide_index=True
        )
        
        # Download as CSV
        csv_data = view_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Student List as CSV",
            data=csv_data,
            file_name=f"students_{selected_branch.replace(' ','_')}.csv",
            mime="text/csv"
        )

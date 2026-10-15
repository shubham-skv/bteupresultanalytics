import streamlit as st
from core.db import clear_students, clear_results, get_student_count, get_result_count

def render():
    st.markdown('<div class="section-header">⚙️ Settings & Data Management</div>', unsafe_allow_html=True)
    st.markdown("Manage your database and application settings here.")

    st.markdown("---")
    st.markdown("### 🗄️ Database Management")

    student_count = get_student_count()
    result_count  = get_result_count()
    from core.db import clear_reval_results, get_reval_count
    reval_count = get_reval_count()

    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-chip"><div class="val">{student_count}</div><div class="lbl">Students in DB</div></div>
      <div class="stat-chip"><div class="val">{result_count}</div><div class="lbl">Results Fetched</div></div>
      <div class="stat-chip"><div class="val">{reval_count}</div><div class="lbl">Reval Checked</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Clear Data")
    st.warning("⚠️ **Warning**: These actions are irreversible and will delete data from your local SQLite database.")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Clear Results Only**
        - Deletes standard fetched marks.
        - Keeps student nominal rolls intact.
        """)
        if st.button("🗑️ Clear Results", use_container_width=True):
            clear_results()
            st.success("✅ All results cleared successfully!")
            st.rerun()

    with col2:
        st.markdown("""
        **Clear REVAL Only**
        - Deletes all fetched REVAL records.
        - Keeps nominal rolls & main marks.
        """)
        if st.button("🗑️ Clear REVAL", use_container_width=True):
            clear_reval_results()
            st.success("✅ All REVAL results cleared successfully!")
            st.rerun()

    with col3:
        st.markdown("""
        **Clear Everything**
        - Deletes all marks & REVAL results.
        - Deletes all nominal rolls (students).
        - Factory resets the database.
        """)
        if st.button("🧨 Flush Database", use_container_width=True):
            clear_results()
            clear_reval_results()
            clear_students()
            st.success("✅ Database flushed successfully!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🏢 Institute Management")
    from core.db import get_institutes, delete_institute_data
    all_insts = get_institutes()
    if all_insts:
        inst_to_delete = st.selectbox("Select Institute to Delete", all_insts)
        st.warning(f"⚠️ This will delete all nominal rolls and fetched results for **{inst_to_delete}**.")
        if st.button("🗑️ Delete Institute Data", type="primary"):
            delete_institute_data(inst_to_delete)
            st.success(f"✅ Data for {inst_to_delete} deleted successfully!")
            st.rerun()
    else:
        st.info("No institutes found in the database.")

    st.markdown("---")
    st.markdown("### 🎨 Theme & Appearance")
    st.info("The application currently uses a customized premium Light theme. To adjust colors further, modify the CSS in `app.py`.")

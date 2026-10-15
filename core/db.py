"""
core/db.py  —  SQLite persistence layer for BTEUP Analytics Suite
"""
import sqlite3
import os
import pandas as pd
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bteup_data.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            name TEXT,
            father_name TEXT,
            dob TEXT,
            branch TEXT,
            semester TEXT,
            rollno TEXT,
            source_file TEXT,
            institute TEXT,
            UNIQUE(enrollment)
        );
        
        -- Migration for existing databases
        BEGIN;
        PRAGMA user_version;
        COMMIT;
        """)
        
        # Add institute column if missing
        try:
            conn.execute("SELECT institute FROM students LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE students ADD COLUMN institute TEXT")
            
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            dob TEXT,
            institute TEXT,
            student_name TEXT,
            father_name TEXT,
            branch TEXT,
            roll_nos TEXT,
            grand_total TEXT,
            paper_code TEXT,
            paper_name TEXT,
            max_marks TEXT,
            min_marks TEXT,
            marks_obtained TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_results_enrollment ON results(enrollment);
        CREATE INDEX IF NOT EXISTS idx_results_branch ON results(branch);
        CREATE INDEX IF NOT EXISTS idx_results_paper ON results(paper_name);

        CREATE TABLE IF NOT EXISTS reval_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            dob TEXT,
            roll_no TEXT,
            institute TEXT,
            student_name TEXT,
            branch TEXT,
            qp_no TEXT,
            paper_name TEXT,
            reval_marks TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'FOUND',
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_reval_enrollment ON reval_results(enrollment);
        CREATE INDEX IF NOT EXISTS idx_reval_institute ON reval_results(institute);
        CREATE INDEX IF NOT EXISTS idx_reval_branch ON reval_results(branch);
        CREATE INDEX IF NOT EXISTS idx_reval_status ON reval_results(status);
        """)


def upsert_students(students: list[dict]):
    """Insert or replace student records."""
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO students (enrollment, name, father_name, dob, branch, semester, rollno, source_file, institute)
            VALUES (:enrollment, :name, :father_name, :dob, :branch, :semester, :rollno, :source_file, :institute)
            ON CONFLICT(enrollment) DO UPDATE SET
                name=excluded.name,
                father_name=excluded.father_name,
                dob=excluded.dob,
                branch=excluded.branch,
                semester=excluded.semester,
                rollno=excluded.rollno,
                source_file=excluded.source_file,
                institute=excluded.institute
        """, students)
    return len(students)


def get_all_students(institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        if institute:
            return pd.read_sql("SELECT * FROM students WHERE institute=? ORDER BY branch, semester, name", conn, params=(institute,))
        return pd.read_sql("SELECT * FROM students ORDER BY branch, semester, name", conn)


def get_institutes() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT institute FROM students WHERE institute IS NOT NULL ORDER BY institute").fetchall()
        return [r[0] for r in rows if r[0]]


def get_branches(institute: str = None) -> list[str]:
    with get_conn() as conn:
        if institute:
            rows = conn.execute("SELECT DISTINCT branch FROM students WHERE institute=? ORDER BY branch", (institute,)).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT branch FROM students ORDER BY branch").fetchall()
        return [r[0] for r in rows if r[0]]


def get_semesters_for_branch(branch: str, institute: str = None) -> list[str]:
    with get_conn() as conn:
        if institute:
            rows = conn.execute(
                "SELECT DISTINCT semester FROM students WHERE branch=? AND institute=? ORDER BY semester", (branch, institute)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT semester FROM students WHERE branch=? ORDER BY semester", (branch,)
            ).fetchall()
        return [r[0] for r in rows if r[0]]


def get_students_for_branch(branch: str, semester: str = None, institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        query = "SELECT * FROM students WHERE branch=?"
        params = [branch]
        
        if semester:
            query += " AND semester=?"
            params.append(semester)
        if institute:
            query += " AND institute=?"
            params.append(institute)
            
        query += " ORDER BY semester, name"
        return pd.read_sql(query, conn, params=params)


def get_already_fetched_enrollments(institute: str = None) -> set:
    with get_conn() as conn:
        if institute:
            rows = conn.execute("""
                SELECT DISTINCT r.enrollment FROM results r
                JOIN students s ON r.enrollment = s.enrollment
                WHERE s.institute = ?
            """, (institute,)).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT enrollment FROM results").fetchall()
        return {r[0] for r in rows}


def insert_results(rows: list[dict]):
    """Insert result rows (subject-level rows). Delete existing first to avoid dups."""
    if not rows:
        return
    enrollments = list({r['enrollment'] for r in rows})
    with get_conn() as conn:
        # Remove old records for these enrollments first
        placeholders = ",".join("?" * len(enrollments))
        conn.execute(f"DELETE FROM results WHERE enrollment IN ({placeholders})", enrollments)
        conn.executemany("""
            INSERT INTO results
                (enrollment, dob, institute, student_name, father_name, branch, roll_nos,
                 grand_total, paper_code, paper_name, max_marks, min_marks, marks_obtained)
            VALUES
                (:enrollment, :dob, :institute, :student_name, :father_name, :branch, :roll_nos,
                 :grand_total, :paper_code, :paper_name, :max_marks, :min_marks, :marks_obtained)
        """, rows)


def get_all_results(institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        if institute:
            # We join with students table to filter results by the student's nominal roll institute
            query = """
                SELECT r.* FROM results r
                JOIN students s ON r.enrollment = s.enrollment
                WHERE s.institute = ?
            """
            return pd.read_sql(query, conn, params=(institute,))
        return pd.read_sql("SELECT * FROM results", conn)


def get_results_for_branch(branch: str) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql(
            "SELECT * FROM results WHERE branch=? ORDER BY student_name", conn, params=(branch,)
        )


def clear_students():
    with get_conn() as conn:
        conn.execute("DELETE FROM students")


def clear_results():
    with get_conn() as conn:
        conn.execute("DELETE FROM results")


def delete_institute_data(institute: str):
    """Delete all students, results, and reval results for a specific institute."""
    with get_conn() as conn:
        conn.execute("DELETE FROM reval_results WHERE enrollment IN (SELECT enrollment FROM students WHERE institute=?) OR institute=?", (institute, institute))
        conn.execute("DELETE FROM results WHERE enrollment IN (SELECT enrollment FROM students WHERE institute=?)", (institute,))
        conn.execute("DELETE FROM students WHERE institute=?", (institute,))


def get_student_count(institute: str = None) -> int:
    with get_conn() as conn:
        if institute:
            return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM students WHERE institute=?", (institute,)).fetchone()[0]
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM students").fetchone()[0]


def get_result_count(institute: str = None) -> int:
    with get_conn() as conn:
        if institute:
            return conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM results r
                JOIN students s ON r.enrollment = s.enrollment
                WHERE s.institute = ?
            """, (institute,)).fetchone()[0]
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM results").fetchone()[0]


def insert_reval_results(rows: list[dict]):
    """Insert or replace reval result rows. Deletes existing first to prevent dups."""
    if not rows:
        return
    enrollments = list({r['enrollment'] for r in rows})
    with get_conn() as conn:
        placeholders = ",".join("?" * len(enrollments))
        conn.execute(f"DELETE FROM reval_results WHERE enrollment IN ({placeholders})", enrollments)
        
        # Enforce institute, student_name, branch, roll_no from students table if missing
        st_map = {}
        st_rows = conn.execute(
            f"SELECT enrollment, name, branch, institute, rollno, dob FROM students WHERE enrollment IN ({placeholders})",
            enrollments
        ).fetchall()
        for sr in st_rows:
            st_map[sr["enrollment"]] = dict(sr)

        enriched_rows = []
        for r in rows:
            enr = r["enrollment"]
            sinfo = st_map.get(enr, {})
            enriched_rows.append({
                "enrollment": enr,
                "dob": r.get("dob") or sinfo.get("dob", ""),
                "roll_no": r.get("roll_no") or sinfo.get("rollno", ""),
                "institute": r.get("institute") or sinfo.get("institute", ""),
                "student_name": r.get("student_name") or sinfo.get("name", ""),
                "branch": r.get("branch") or sinfo.get("branch", ""),
                "qp_no": str(r.get("qp_no", "")).strip(),
                "paper_name": str(r.get("paper_name", "")).strip(),
                "reval_marks": str(r.get("reval_marks", "")).strip(),
                "remarks": str(r.get("remarks", "")).strip(),
                "status": str(r.get("status", "FOUND")).strip(),
            })

        conn.executemany("""
            INSERT INTO reval_results
                (enrollment, dob, roll_no, institute, student_name, branch, qp_no,
                 paper_name, reval_marks, remarks, status)
            VALUES
                (:enrollment, :dob, :roll_no, :institute, :student_name, :branch, :qp_no,
                 :paper_name, :reval_marks, :remarks, :status)
        """, enriched_rows)


def get_all_reval_results(institute: str = None) -> pd.DataFrame:
    """Fetch all reval results, joining student metadata where possible."""
    with get_conn() as conn:
        if institute:
            query = """
                SELECT 
                    r.id,
                    r.enrollment,
                    COALESCE(NULLIF(r.dob, ''), s.dob) AS dob,
                    COALESCE(NULLIF(r.roll_no, ''), s.rollno) AS roll_no,
                    COALESCE(NULLIF(r.institute, ''), s.institute) AS institute,
                    COALESCE(NULLIF(r.student_name, ''), s.name) AS student_name,
                    COALESCE(NULLIF(r.branch, ''), s.branch) AS branch,
                    r.qp_no,
                    r.paper_name,
                    r.reval_marks,
                    r.remarks,
                    r.status,
                    r.fetched_at
                FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ? OR (r.institute IS NULL AND s.institute IS NULL))
                ORDER BY branch, student_name, qp_no
            """
            res = pd.read_sql(query, conn, params=(institute, institute))
            if not res.empty:
                return res
        
        query = """
            SELECT 
                r.id,
                r.enrollment,
                COALESCE(NULLIF(r.dob, ''), s.dob) AS dob,
                COALESCE(NULLIF(r.roll_no, ''), s.rollno) AS roll_no,
                COALESCE(NULLIF(r.institute, ''), s.institute) AS institute,
                COALESCE(NULLIF(r.student_name, ''), s.name) AS student_name,
                COALESCE(NULLIF(r.branch, ''), s.branch) AS branch,
                r.qp_no,
                r.paper_name,
                r.reval_marks,
                r.remarks,
                r.status,
                r.fetched_at
            FROM reval_results r
            LEFT JOIN students s ON r.enrollment = s.enrollment
            ORDER BY branch, student_name, qp_no
        """
        return pd.read_sql(query, conn)


def get_already_checked_reval_enrollments(institute: str = None) -> set:
    with get_conn() as conn:
        if institute:
            rows = conn.execute("""
                SELECT DISTINCT r.enrollment FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?)
            """, (institute, institute)).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT enrollment FROM reval_results").fetchall()
        return {r[0] for r in rows if r[0]}


def get_reval_count(institute: str = None) -> int:
    with get_conn() as conn:
        if institute:
            return conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?)
            """, (institute, institute)).fetchone()[0]
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM reval_results").fetchone()[0]


def get_reval_stats(institute: str = None) -> dict:
    with get_conn() as conn:
        if institute:
            total = conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?)
            """, (institute, institute)).fetchone()[0]
            found = conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?) AND r.status = 'FOUND'
            """, (institute, institute)).fetchone()[0]
            not_found = conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?) AND r.status != 'FOUND'
            """, (institute, institute)).fetchone()[0]
            subjects = conn.execute("""
                SELECT COUNT(*) FROM reval_results r
                LEFT JOIN students s ON r.enrollment = s.enrollment
                WHERE (r.institute = ? OR s.institute = ?) AND r.status = 'FOUND'
            """, (institute, institute)).fetchone()[0]
        else:
            total = conn.execute("SELECT COUNT(DISTINCT enrollment) FROM reval_results").fetchone()[0]
            found = conn.execute("SELECT COUNT(DISTINCT enrollment) FROM reval_results WHERE status = 'FOUND'").fetchone()[0]
            not_found = conn.execute("SELECT COUNT(DISTINCT enrollment) FROM reval_results WHERE status != 'FOUND'").fetchone()[0]
            subjects = conn.execute("SELECT COUNT(*) FROM reval_results WHERE status = 'FOUND'").fetchone()[0]

        return {
            "total_checked": total,
            "found": found,
            "not_found": not_found,
            "subjects_found": subjects
        }


def clear_reval_results(institute: str = None):
    with get_conn() as conn:
        if institute:
            conn.execute("""
                DELETE FROM reval_results WHERE enrollment IN (
                    SELECT enrollment FROM students WHERE institute = ?
                ) OR institute = ?
            """, (institute, institute))
        else:
            conn.execute("DELETE FROM reval_results")


def get_failed_students(institute: str = None, branch: str = None) -> pd.DataFrame:
    """
    Get students who failed or had back papers in any theory subject.
    Useful for targeting REVAL checks!
    """
    with get_conn() as conn:
        query = """
            SELECT DISTINCT s.enrollment, s.name, s.father_name, s.dob, s.branch, s.semester, s.rollno, s.institute
            FROM students s
            JOIN results r ON s.enrollment = r.enrollment
            WHERE (
                CAST(r.marks_obtained AS INTEGER) < CAST(r.min_marks AS INTEGER)
                AND CAST(r.min_marks AS INTEGER) > 0
                AND UPPER(r.paper_name) NOT LIKE '%CARRY OVER%'
            )
        """
        params = []
        if institute:
            query += " AND s.institute = ?"
            params.append(institute)
        if branch:
            query += " AND s.branch = ?"
            params.append(branch)
        query += " ORDER BY s.branch, s.name"
        return pd.read_sql(query, conn, params=params)


def apply_reval_to_results(institute: str = None) -> int:
    """
    Permanently updates the marks_obtained in the results table
    with the re-evaluation marks from reval_results.
    Returns the number of updated records.
    """
    with get_conn() as conn:
        query = """
            SELECT r.enrollment, r.paper_name, r.reval_marks
            FROM reval_results r
            WHERE r.status = 'FOUND'
        """
        params = []
        if institute:
            query += " AND (r.institute = ? OR r.enrollment IN (SELECT enrollment FROM students WHERE institute = ?))"
            params.extend([institute, institute])
            
        rows = conn.execute(query, params).fetchall()
        updated_count = 0
        for enr, pname, rev_m in rows:
            rev_str = str(rev_m).strip()
            if rev_str.isdigit():
                p_clean = pname.strip()
                res = conn.execute("""
                    UPDATE results
                    SET marks_obtained = ?
                    WHERE enrollment = ?
                      AND (UPPER(paper_name) = UPPER(?) 
                           OR UPPER(paper_name) = UPPER(?) 
                           OR UPPER(paper_name) = UPPER(?))
                      AND (CAST(max_marks AS INTEGER) >= 50 OR CAST(min_marks AS INTEGER) >= 17)
                """, (rev_str, enr, p_clean, p_clean.replace('-', ' - '), p_clean.replace(' - ', '-')))
                updated_count += res.rowcount
        return updated_count


# Initialise on import
init_db()

